package bridge

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestMetricsExportContainsOnlyResourceGauges(t *testing.T) {
	t.Setenv("SECRET_TOKEN", "metrics-secret-canary")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		data, _ := io.ReadAll(r.Body)
		if !json.Valid(data) || strings.Contains(string(data), "metrics-secret-canary") {
			t.Error("invalid metrics or secret leak")
		}
		if !strings.Contains(string(data), "bridge.process.heap.allocated") || r.Header.Get("Content-Type") != "application/json" {
			t.Error("missing OTLP gauge")
		}
		w.WriteHeader(200)
	}))
	defer server.Close()
	if err := ExportMetrics(context.Background(), server.URL+"/v1/metrics"); err != nil {
		t.Fatal(err)
	}
	for _, url := range []string{"http://example.com/metrics", "https://user:secret@example.com/metrics", "https://example.com/metrics?token=secret"} {
		if ValidateMetricsURL(url) == nil {
			t.Fatal("unsafe URL accepted")
		}
	}
}
