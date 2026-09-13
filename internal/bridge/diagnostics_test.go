package bridge

import (
	"bytes"
	"context"
	"github.com/coder/websocket"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestDoctorRequiresRPCAndDoesNotClaimMCPHealth(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	socket := mockNative(t, func(c *websocket.Conn) {
		_, _, err := c.Read(ctx)
		if err != nil {
			return
		}
		c.Write(ctx, websocket.MessageText, []byte(`{"id":1,"result":{"userAgent":"test"}}`))
		c.Read(ctx)
	})
	h := (Config{Socket: socket}).Health(ctx)
	if h.Protocol != "connected" || h.Status != "degraded" || h.MCP != "unknown" {
		t.Fatal(h)
	}
}
func TestDiagnosticLogsContainOnlyDeclaredMetadata(t *testing.T) {
	dir := t.TempDir()
	log, err := NewLog(dir)
	if err != nil {
		t.Fatal(err)
	}
	log.Emit("terminal_started")
	log.Close()
	var out bytes.Buffer
	if err = (Config{Data: dir}).ReadLogs(&out); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out.String(), "terminal_started") {
		t.Fatal("missing event")
	}
	if strings.Contains(out.String(), "HOME") || strings.Contains(out.String(), "PATH") {
		t.Fatal("environment leaked")
	}
	entries, _ := os.ReadDir(filepath.Join(dir, "logs"))
	for _, e := range entries {
		i, _ := e.Info()
		if i.Mode().Perm() != 0600 {
			t.Fatal("log not private")
		}
	}
}
func TestDiagnosticsExcludeSavedData(t *testing.T) {
	dir := t.TempDir()
	secret := "secret-support-canary"
	os.WriteFile(filepath.Join(dir, "auth.json"), []byte(secret), 0600)
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	var out bytes.Buffer
	if err := (Config{Data: dir, Socket: filepath.Join(dir, "missing.sock")}).Support(ctx, &out); err != nil {
		t.Fatal(err)
	}
	if strings.Contains(out.String(), secret) || strings.Contains(out.String(), dir) {
		t.Fatal("private data leaked")
	}
}
