package bridge

import (
	"encoding/xml"
	"strings"
	"testing"
)

func TestServiceOnlyStartsBridgeAndEscapesPaths(t *testing.T) {
	t.Setenv("SECRET_TOKEN", "must-not-be-in-plist")
	t.Setenv("PATH", "/opt/homebrew/bin:/Users/test/.local/bin")
	c := Config{Root: "/tmp/A & B", Data: "/tmp/test-data", CodexHome: "/tmp/codex", Node: "/bundle/node/bin/node", Codex: "/bundle/codex/bin/codex", Host: "127.0.0.1", Port: 18773}
	data := c.ServicePlist()
	var parsed any
	if err := xml.Unmarshal(data, &parsed); err != nil {
		t.Fatal(err)
	}
	text := string(data)
	for _, bad := range []string{"must-not-be-in-plist", "daemon-start", "launchctl submit", "<key>KeepAlive</key><true/>"} {
		if strings.Contains(text, bad) {
			t.Fatal("unsafe service", bad)
		}
	}
	for _, good := range []string{"A &amp; B/bin/bridge", "<string>serve</string>", "/opt/homebrew/bin", ".local/bin", "<key>KeepAlive</key><false/>"} {
		if !strings.Contains(text, good) {
			t.Fatal("missing", good)
		}
	}
}
