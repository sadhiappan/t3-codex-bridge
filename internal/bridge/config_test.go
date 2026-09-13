package bridge

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestEnvironmentIsolation(t *testing.T) {
	t.Setenv("PATH", "/test/bin")
	t.Setenv("VITE_WS_URL", "http://wrong")
	t.Setenv("T3_CODEX_SHARED_PROJECTS", "[\"/all\"]")
	t.Setenv("T3CODE_OTLP_TRACES_URL", "https://unrequested.example")
	t.Setenv("T3CODE_TELEMETRY_ENABLED", "true")
	c := Config{Node: "/bundle/node/bin/node", Codex: "/bundle/codex/bin/codex", CodexHome: "/isolated", Data: "/data", Socket: "/isolated/sock", Registrations: "/data/registrations"}
	env := map[string]string{}
	for _, v := range c.Environment() {
		k, v, _ := strings.Cut(v, "=")
		env[k] = v
	}
	if _, ok := env["VITE_WS_URL"]; ok {
		t.Fatal("baked origin leaked")
	}
	if env["T3_CODEX_SHARED_PROJECTS"] != "[]" || env["T3_CODEX_START_DAEMON"] != "0" {
		t.Fatal("opt in lost")
	}
	if env["T3CODE_TELEMETRY_ENABLED"] != "false" {
		t.Fatal("analytics enabled")
	}
	if _, ok := env["T3CODE_OTLP_TRACES_URL"]; ok {
		t.Fatal("unrequested telemetry export")
	}
	if !strings.HasSuffix(env["PATH"], ":/test/bin") {
		t.Fatal("host tool PATH lost")
	}
}
func TestConfigHonorsMattHostAndPort(t *testing.T) {
	root := t.TempDir()
	os.WriteFile(filepath.Join(root, "versions.json"), []byte(`{"codex":"0.154.0","node":"24.13.1"}`), 0600)
	t.Setenv("T3_BRIDGE_HOST", "192.0.2.10")
	t.Setenv("T3_BRIDGE_PORT", "18774")
	t.Setenv("CODEX_HOME", "/tmp/codex test")
	c, err := LoadConfig(root)
	if err != nil {
		t.Fatal(err)
	}
	if c.Address() != "192.0.2.10:18774" || c.Socket != "/tmp/codex test/app-server-control/app-server-control.sock" {
		t.Fatal(c)
	}
	for _, port := range []string{"80", "65536", "bad", "1.1"} {
		t.Setenv("T3_BRIDGE_PORT", port)
		if _, err := LoadConfig(root); err == nil {
			t.Fatal("invalid port accepted")
		}
	}
}
