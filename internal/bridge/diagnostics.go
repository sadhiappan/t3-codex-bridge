package bridge

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"sync/atomic"
	"time"

	"golang.org/x/sys/unix"
)

var logName = regexp.MustCompile(`^bridge-[0-9]+\.jsonl(\.1)?$`)

type Event struct {
	Time  time.Time `json:"time"`
	PID   int       `json:"pid"`
	Event string    `json:"event"`
}
type Log struct {
	queue   chan Event
	done    chan struct{}
	dropped atomic.Uint64
	dir     string
}

func NewLog(data string) (*Log, error) {
	dir := filepath.Join(data, "logs")
	if err := os.MkdirAll(dir, 0700); err != nil {
		return nil, err
	}
	l := &Log{queue: make(chan Event, 128), done: make(chan struct{}), dir: dir}
	go func() {
		defer close(l.done)
		for e := range l.queue {
			if l.write(e) != nil {
				l.dropped.Add(1)
			}
		}
	}()
	return l, nil
}
func (l *Log) Emit(event string) {
	select {
	case l.queue <- Event{Time: time.Now().UTC(), PID: os.Getpid(), Event: event}:
	default:
		l.dropped.Add(1)
	}
}
func (l *Log) Close() {
	close(l.queue)
	select {
	case <-l.done:
	case <-time.After(2 * time.Second):
	}
	if l.dropped.Load() > 0 {
		fmt.Fprintln(os.Stderr, "Bridge diagnostics dropped records; check disk space and permissions.")
	}
}
func (l *Log) write(e Event) error {
	lock, err := os.OpenFile(filepath.Join(l.dir, ".lock"), os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return err
	}
	defer lock.Close()
	if err = unix.Flock(int(lock.Fd()), unix.LOCK_EX|unix.LOCK_NB); err != nil {
		return err
	}
	defer unix.Flock(int(lock.Fd()), unix.LOCK_UN)
	path := filepath.Join(l.dir, fmt.Sprintf("bridge-%d.jsonl", os.Getpid()))
	if info, err := os.Stat(path); err == nil && info.Size() >= 10<<20 {
		if err = os.Rename(path, path+".1"); err != nil {
			return err
		}
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0600)
	if err != nil {
		return err
	}
	err = json.NewEncoder(f).Encode(e)
	closeErr := f.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	entries, err := os.ReadDir(l.dir)
	if err != nil {
		return err
	}
	var infos []os.FileInfo
	var total int64
	for _, entry := range entries {
		if !logName.MatchString(entry.Name()) {
			continue
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() {
			continue
		}
		infos = append(infos, info)
		total += info.Size()
	}
	sort.Slice(infos, func(i, j int) bool { return infos[i].ModTime().Before(infos[j].ModTime()) })
	for _, info := range infos {
		if time.Since(info.ModTime()) <= 7*24*time.Hour && total <= 200<<20 {
			continue
		}
		if err = os.Remove(filepath.Join(l.dir, info.Name())); err != nil {
			return err
		}
		total -= info.Size()
	}
	return nil
}

type Health struct {
	Schema        int    `json:"schemaVersion"`
	Status        string `json:"status"`
	CodexExpected string `json:"codexExpected"`
	Protocol      string `json:"protocol"`
	MCP           string `json:"mcp"`
	Error         string `json:"error,omitempty"`
	FileLimit     uint64 `json:"fileLimit"`
}

func (c Config) Health(ctx context.Context) Health {
	h := Health{Schema: 1, Status: "unavailable", CodexExpected: c.Versions.Codex, Protocol: "unavailable", MCP: "unknown"}
	var limit unix.Rlimit
	if unix.Getrlimit(unix.RLIMIT_NOFILE, &limit) == nil {
		h.FileLimit = limit.Cur
	}
	connect, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	client, err := DialUnix(connect, c.Socket)
	if err != nil {
		h.Error = "daemon_unreachable"
		return h
	}
	defer client.CloseNow()
	if err = client.Write(connect, 1, []byte(`{"id":1,"method":"initialize","params":{"clientInfo":{"name":"t3_bridge_doctor","version":"0.2.0"},"capabilities":{"experimentalApi":true}}}`)); err != nil {
		h.Error = "initialize_failed"
		return h
	}
	for {
		_, data, err := client.Read(connect)
		if err != nil {
			h.Error = "initialize_failed"
			return h
		}
		var result struct {
			ID     json.RawMessage `json:"id"`
			Result json.RawMessage `json:"result"`
			Error  json.RawMessage `json:"error"`
		}
		if json.Unmarshal(data, &result) != nil {
			h.Error = "invalid_protocol_response"
			return h
		}
		if string(result.ID) != "1" {
			continue
		}
		if len(result.Error) > 0 || len(result.Result) == 0 {
			h.Error = "initialize_rejected"
			return h
		}
		if err = client.Write(connect, 1, []byte(`{"method":"initialized"}`)); err != nil {
			h.Error = "initialize_failed"
			return h
		}
		h.Protocol = "connected"
		h.Status = "degraded"
		return h
	}
}
func (c Config) Support(ctx context.Context, out io.Writer) error {
	// An allowlisted health report only; never collect databases, environments or raw child output.
	return json.NewEncoder(out).Encode(struct {
		Health       Health            `json:"health"`
		Capabilities map[string]string `json:"capabilities"`
	}{c.Health(ctx), Capabilities()})
}
func Capabilities() map[string]string {
	return map[string]string{
		"sharedHistory": "text-only", "fileRollback": "unsupported", "dynamicT3MCP": "unsupported", "persistentSettingsSync": "unverified", "nativeMCPHealth": "requires-session-verification",
	}
}

func (c Config) ReadLogs(out io.Writer) error {
	entries, err := os.ReadDir(filepath.Join(c.Data, "logs"))
	if err != nil {
		return err
	}
	for _, entry := range entries {
		if !logName.MatchString(entry.Name()) || !entry.Type().IsRegular() {
			continue
		}
		f, err := os.Open(filepath.Join(c.Data, "logs", entry.Name()))
		if err != nil {
			return err
		}
		_, err = io.Copy(out, io.LimitReader(f, 10<<20))
		f.Close()
		if err != nil {
			return err
		}
	}
	return nil
}
