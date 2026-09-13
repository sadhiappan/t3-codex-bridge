package bridge

import (
	"bytes"
	"context"
	"errors"
	"github.com/coder/websocket"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestChildPreservesArgumentsAndExitStatus(t *testing.T) {
	var out bytes.Buffer
	err := RunChild(context.Background(), "/bin/sh", []string{"-c", `printf '%s' "$1"; exit 7`, "sh", "a; $(echo secret)"}, nil, &out, &out)
	var exit *exec.ExitError
	if !errors.As(err, &exit) || exit.ExitCode() != 7 {
		t.Fatalf("exit %v", err)
	}
	if out.String() != "a; $(echo secret)" {
		t.Fatal("arguments interpreted by shell")
	}
}
func TestChildCancellationReapsOwnedProcess(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()
	err := RunChild(ctx, "/bin/sleep", []string{"60"}, nil, &bytes.Buffer{}, &bytes.Buffer{})
	if err == nil {
		t.Fatal("expected terminated child")
	}
}

func TestServeStopsAfterThreeRetriesWithoutRestartingNative(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	socket := mockNative(t, func(c *websocket.Conn) {
		if _, _, err := c.Read(ctx); err != nil {
			return
		}
		c.Write(ctx, websocket.MessageText, []byte(`{"id":1,"result":{}}`))
		c.Read(ctx)
	})
	dir := t.TempDir()
	os.MkdirAll(filepath.Join(dir, "t3"), 0700)
	script := filepath.Join(dir, "fail.sh")
	os.WriteFile(script, []byte("printf x >> \"$T3CODE_HOME/../attempts\"\nexit 1\n"), 0700)
	log, err := NewLog(dir)
	if err != nil {
		t.Fatal(err)
	}
	defer log.Close()
	err = (Config{Data: dir, Node: "/bin/sh", Server: script, Socket: socket}).Serve(ctx, log)
	if err == nil || !strings.Contains(err.Error(), "failed repeatedly") {
		t.Fatalf("unexpected recovery result %v", err)
	}
	attempts, err := os.ReadFile(filepath.Join(dir, "attempts"))
	if err != nil {
		t.Fatal(err)
	}
	if string(attempts) != "xxxx" {
		t.Fatalf("unbounded recovery: %q", attempts)
	}
}
