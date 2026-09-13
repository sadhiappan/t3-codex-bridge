package bridge

import (
	"bytes"
	"context"
	"encoding/json"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"testing"
	"time"

	"github.com/coder/websocket"
)

func mockNative(t testing.TB, handler func(*websocket.Conn)) string {
	t.Helper()
	dir, err := os.MkdirTemp("/tmp", "native-test-")
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(dir, "rpc.sock")
	l, err := net.Listen("unix", path)
	if err != nil {
		t.Fatal(err)
	}
	var wg sync.WaitGroup
	server := &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Sec-WebSocket-Extensions") != "" {
			t.Error("compression offered")
		}
		c, err := websocket.Accept(w, r, nil)
		if err != nil {
			return
		}
		wg.Add(1)
		defer wg.Done()
		defer c.CloseNow()
		c.SetReadLimit(64 << 20)
		handler(c)
	})}
	go server.Serve(l)
	t.Cleanup(func() { server.Close(); wg.Wait(); os.RemoveAll(dir) })
	return path
}
func TestRelayPreservesFramesAndRegistersOnlyRootOpens(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	upstream := mockNative(t, func(c *websocket.Conn) {
		for {
			kind, data, err := c.Read(ctx)
			if err != nil {
				return
			}
			if err = c.Write(ctx, kind, data); err != nil {
				return
			}
		}
	})
	var mu sync.Mutex
	ids := []string{}
	relay, err := StartRelay(ctx, upstream, func(id string) { mu.Lock(); defer mu.Unlock(); ids = append(ids, id) }, func(string) {})
	if err != nil {
		t.Fatal(err)
	}
	defer relay.Close()
	c, err := DialUnix(ctx, relay.Socket)
	if err != nil {
		t.Fatal(err)
	}
	defer c.CloseNow()
	frames := [][]byte{
		[]byte(`{"id":1,"method":"thread/read"}`), []byte(`{"id":1,"result":{"thread":{"id":"picker"}}}`),
		[]byte(`{"id":2,"method":"thread/resume"}`), []byte(`{"id":2,"result":{"thread":{"id":"root"}}}`),
		[]byte(`{"id":3,"method":"thread/start"}`), []byte(`{"id":3,"result":{"thread":{"id":"child","parentThreadId":"root"}}}`),
		[]byte(`{"id":4,"method":"thread/start"}`), []byte(`{"id":4,"result":{"thread":{"id":"ephemeral","ephemeral":true}}}`),
		[]byte(`{"id":5,"method":"thread/resume"}`),
		[]byte(`{"id":5,"result":{"padding":"` + string(bytes.Repeat([]byte("x"), 128<<10)) + `","thread":{"id":"large-root"}}}`),
		bytes.Repeat([]byte("x"), 2<<20),
	}
	for i, payload := range frames {
		kind := websocket.MessageText
		if i == len(frames)-1 {
			kind = websocket.MessageBinary
		}
		if err = c.Write(ctx, kind, payload); err != nil {
			t.Fatal(err)
		}
		gotKind, got, err := c.Read(ctx)
		if err != nil || gotKind != kind || !bytes.Equal(got, payload) {
			t.Fatalf("frame %d changed: %v", i, err)
		}
	}
	mu.Lock()
	defer mu.Unlock()
	if len(ids) != 2 || ids[0] != "root" || ids[1] != "large-root" {
		t.Fatalf("associations %v", ids)
	}
}
func TestRelayCloseReleasesIdlePeersAndSocket(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	upstream := mockNative(t, func(c *websocket.Conn) {
		for {
			_, _, err := c.Read(ctx)
			if err != nil {
				return
			}
		}
	})
	r, err := StartRelay(ctx, upstream, func(string) {}, func(string) {})
	if err != nil {
		t.Fatal(err)
	}
	c, err := DialUnix(ctx, r.Socket)
	if err != nil {
		t.Fatal(err)
	}
	defer c.CloseNow()
	if err = r.Close(); err != nil {
		t.Fatal(err)
	}
	if _, err = os.Stat(r.Socket); !os.IsNotExist(err) {
		t.Fatal("socket retained")
	}
	if _, _, err = c.Read(ctx); err == nil {
		t.Fatal("peer retained")
	}
}
func TestObserverBoundedAndIgnoresUnmatchedResponses(t *testing.T) {
	o := observer{}
	for i := 0; i < 1000; i++ {
		data, _ := json.Marshal(map[string]any{"id": i, "method": "thread/start"})
		o.observe(data, false)
	}
	if len(o.pending) > 128 {
		t.Fatal("unbounded pending requests")
	}
	if got := o.observe([]byte(`{"id":"0","result":{"thread":{"id":"wrong"}}}`), true); got != "" {
		t.Fatal("string and numeric IDs conflated")
	}
}

func TestRelayReconnectResourceBound(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	upstream := mockNative(t, func(c *websocket.Conn) {
		for {
			kind, data, err := c.Read(ctx)
			if err != nil {
				return
			}
			if c.Write(ctx, kind, data) != nil {
				return
			}
		}
	})
	before, _ := os.ReadDir("/dev/fd")
	r, err := StartRelay(ctx, upstream, func(string) {}, func(string) {})
	if err != nil {
		t.Fatal(err)
	}
	cycles := 100
	if os.Getenv("T3_BRIDGE_STRESS") == "1" {
		cycles = 1000
	}
	for i := 0; i < cycles; i++ {
		c, err := DialUnix(ctx, r.Socket)
		if err != nil {
			t.Fatal(err)
		}
		if err = c.Write(ctx, websocket.MessageText, []byte(`{"method":"ping"}`)); err != nil {
			t.Fatal(err)
		}
		if _, _, err = c.Read(ctx); err != nil {
			t.Fatal(err)
		}
		c.CloseNow()
	}
	if err = r.Close(); err != nil {
		t.Fatal(err)
	}
	after, _ := os.ReadDir("/dev/fd")
	if len(before) > 0 && len(after) > len(before)+2 {
		t.Fatalf("descriptor growth: %d -> %d", len(before), len(after))
	}
	t.Logf("%d reconnects; descriptors %d -> %d", cycles, len(before), len(after))
}

func BenchmarkRoundtrip(b *testing.B) {
	for _, relayed := range []bool{false, true} {
		name := "direct"
		if relayed {
			name = "relay"
		}
		b.Run(name, func(b *testing.B) {
			ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
			defer cancel()
			socket := mockNative(b, func(c *websocket.Conn) {
				for {
					kind, data, err := c.Read(ctx)
					if err != nil {
						return
					}
					if c.Write(ctx, kind, data) != nil {
						return
					}
				}
			})
			if relayed {
				r, err := StartRelay(ctx, socket, func(string) {}, func(string) {})
				if err != nil {
					b.Fatal(err)
				}
				defer r.Close()
				socket = r.Socket
			}
			c, err := DialUnix(ctx, socket)
			if err != nil {
				b.Fatal(err)
			}
			defer c.CloseNow()
			durations := make([]time.Duration, 0, b.N)
			payload := []byte(`{"id":1,"method":"ping"}`)
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				start := time.Now()
				if err = c.Write(ctx, websocket.MessageText, payload); err != nil {
					b.Fatal(err)
				}
				if _, _, err = c.Read(ctx); err != nil {
					b.Fatal(err)
				}
				durations = append(durations, time.Since(start))
			}
			b.StopTimer()
			sort.Slice(durations, func(i, j int) bool { return durations[i] < durations[j] })
			b.ReportMetric(float64(durations[(len(durations)-1)*95/100].Nanoseconds())/1e6, "p95-ms")
		})
	}
}
