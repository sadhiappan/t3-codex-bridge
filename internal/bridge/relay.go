package bridge

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/coder/websocket"
)

type Relay struct {
	Socket  string
	cancel  context.CancelFunc
	server  *http.Server
	wg      sync.WaitGroup
	mu      sync.Mutex
	closing bool
	dir     string
}

type openRequest struct{ at time.Time }
type observer struct{ pending map[string]openRequest }

func (o *observer) observe(data []byte, incoming bool) string {
	var f struct {
		ID     json.RawMessage `json:"id"`
		Method string          `json:"method"`
		Result struct {
			Thread struct {
				ID        string  `json:"id"`
				Ephemeral bool    `json:"ephemeral"`
				Parent    *string `json:"parentThreadId"`
			} `json:"thread"`
		} `json:"result"`
	}
	if json.Unmarshal(data, &f) != nil {
		return ""
	}
	now := time.Now()
	for id, p := range o.pending {
		if now.Sub(p.at) > time.Minute {
			delete(o.pending, id)
		}
	}
	if !incoming {
		if len(f.ID) > 0 && (f.Method == "thread/start" || f.Method == "thread/resume" || f.Method == "thread/fork") {
			if o.pending == nil {
				o.pending = map[string]openRequest{}
			}
			if len(o.pending) < 128 {
				o.pending[string(f.ID)] = openRequest{now}
			}
		}
		return ""
	}
	if f.Method != "" {
		return ""
	}
	if _, ok := o.pending[string(f.ID)]; !ok {
		return ""
	}
	delete(o.pending, string(f.ID))
	if f.Result.Thread.Ephemeral || f.Result.Thread.Parent != nil {
		return ""
	}
	if identity.MatchString(f.Result.Thread.ID) {
		return f.Result.Thread.ID
	}
	return ""
}

func DialUnix(ctx context.Context, path string) (*websocket.Conn, error) {
	transport := &http.Transport{DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
		return (&net.Dialer{}).DialContext(ctx, "unix", path)
	}}
	c, _, err := websocket.Dial(ctx, "ws://localhost/", &websocket.DialOptions{HTTPClient: &http.Client{Transport: transport}, CompressionMode: websocket.CompressionDisabled})
	transport.CloseIdleConnections()
	if c != nil {
		c.SetReadLimit(64 << 20)
	}
	return c, err
}

func StartRelay(ctx context.Context, upstream string, onThread func(string), onError func(string)) (*Relay, error) {
	if !filepath.IsAbs(upstream) {
		return nil, fmt.Errorf("native socket path must be absolute")
	}
	dir, err := os.MkdirTemp("/tmp", "t3-relay-")
	if err != nil {
		return nil, err
	}
	socket := filepath.Join(dir, "rpc.sock")
	listener, err := net.Listen("unix", socket)
	if err != nil {
		os.RemoveAll(dir)
		return nil, err
	}
	if err = os.Chmod(socket, 0600); err != nil {
		listener.Close()
		os.RemoveAll(dir)
		return nil, err
	}
	lifetime, cancel := context.WithCancel(ctx)
	r := &Relay{Socket: socket, cancel: cancel, dir: dir}
	r.server = &http.Server{ReadHeaderTimeout: 5 * time.Second, Handler: http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		r.mu.Lock()
		if r.closing {
			r.mu.Unlock()
			http.Error(w, "closing", 503)
			return
		}
		r.wg.Add(1)
		r.mu.Unlock()
		defer r.wg.Done()
		terminal, err := websocket.Accept(w, req, &websocket.AcceptOptions{CompressionMode: websocket.CompressionDisabled})
		if err != nil {
			return
		}
		defer terminal.CloseNow()
		terminal.SetReadLimit(64 << 20)
		connect, stop := context.WithTimeout(lifetime, 5*time.Second)
		native, err := DialUnix(connect, upstream)
		stop()
		if err != nil {
			onError("upstream_connect_failed")
			return
		}
		defer native.CloseNow()
		pair, closePair := context.WithCancel(lifetime)
		defer closePair()
		var observationMu sync.Mutex
		obs := observer{}
		pump := func(source, target *websocket.Conn, incoming bool) error {
			for {
				kind, reader, err := source.Reader(pair)
				if err != nil {
					return err
				}
				writer, err := target.Writer(pair, kind)
				if err != nil {
					return err
				}
				// Native resume responses include history; inspect complete text messages up to the protocol limit.
				var prefix []byte
				if kind == websocket.MessageText {
					prefix, err = io.ReadAll(io.LimitReader(reader, (64<<20)+1))
					if err != nil {
						return err
					}
					observationMu.Lock()
					id := ""
					if len(prefix) <= 64<<20 {
						id = obs.observe(prefix, incoming)
					}
					observationMu.Unlock()
					if id != "" {
						onThread(id)
					}
					if _, err = writer.Write(prefix); err != nil {
						return err
					}
				}
				if _, err = io.Copy(writer, reader); err != nil {
					return err
				}
				if err = writer.Close(); err != nil {
					return err
				}
			}
		}
		done := make(chan error, 2)
		go func() { done <- pump(terminal, native, false) }()
		go func() { done <- pump(native, terminal, true) }()
		err = <-done
		closePair()
		terminal.CloseNow()
		native.CloseNow()
		<-done
		if lifetime.Err() == nil && websocket.CloseStatus(err) != websocket.StatusNormalClosure && websocket.CloseStatus(err) != websocket.StatusGoingAway {
			onError("connection_closed")
		}
	})}
	r.wg.Add(1)
	go func() {
		defer r.wg.Done()
		if err := r.server.Serve(listener); err != nil && err != http.ErrServerClosed {
			onError("relay_listener_failed")
		}
	}()
	return r, nil
}
func (r *Relay) Close() error {
	r.mu.Lock()
	r.closing = true
	r.mu.Unlock()
	r.cancel()
	err := r.server.Close()
	r.wg.Wait()
	cleanup := os.RemoveAll(r.dir)
	if err != nil {
		return err
	}
	return cleanup
}
