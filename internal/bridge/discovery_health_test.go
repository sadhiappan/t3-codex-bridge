package bridge

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestDiscoveryHealth(t *testing.T) {
	dir := t.TempDir()
	now := time.Date(2026, 9, 14, 0, 0, 0, 0, time.UTC)
	if got := discoveryHealth(dir, now); got != "unknown" {
		t.Fatal(got)
	}
	for _, tc := range []struct{ body, want string }{
		{`{"status":"healthy","checkedAt":"2026-09-14T00:00:00Z"}`, "healthy"},
		{`{"status":"degraded","checkedAt":"2026-09-14T00:00:00Z"}`, "degraded"},
		{`{"status":"disconnected","checkedAt":"2026-09-14T00:00:00Z"}`, "disconnected"},
		{`{"status":"healthy","checkedAt":"2026-09-13T00:00:00Z"}`, "stale"},
		{`{"status":"healthy","checkedAt":"2026-09-15T00:00:00Z"}`, "stale"},
		{`{"status":"unexpected","checkedAt":"2026-09-14T00:00:00Z"}`, "invalid"},
		{`{`, "invalid"},
	} {
		if err := os.WriteFile(filepath.Join(dir, "discovery-health.json"), []byte(tc.body), 0600); err != nil {
			t.Fatal(err)
		}
		if got := discoveryHealth(dir, now); got != tc.want {
			t.Errorf("got %s, want %s", got, tc.want)
		}
	}
}
