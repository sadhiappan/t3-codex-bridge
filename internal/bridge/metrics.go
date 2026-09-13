package bridge

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"runtime"
	"strconv"
	"time"
)

func MetricsPayload() []byte {
	var memory runtime.MemStats
	runtime.ReadMemStats(&memory)
	point := func(name, unit string, value uint64) any {
		return map[string]any{"name": name, "unit": unit, "gauge": map[string]any{"dataPoints": []any{map[string]any{"timeUnixNano": strconv.FormatInt(time.Now().UnixNano(), 10), "asInt": strconv.FormatUint(value, 10)}}}}
	}
	payload := map[string]any{"resourceMetrics": []any{map[string]any{
		"resource":     map[string]any{"attributes": []any{map[string]any{"key": "service.name", "value": map[string]string{"stringValue": "t3-codex-bridge"}}, map[string]any{"key": "process.pid", "value": map[string]string{"intValue": strconv.Itoa(os.Getpid())}}}},
		"scopeMetrics": []any{map[string]any{"scope": map[string]string{"name": "t3-codex-bridge"}, "metrics": []any{point("bridge.process.goroutines", "{goroutine}", uint64(runtime.NumGoroutine())), point("bridge.process.heap.allocated", "By", memory.HeapAlloc)}}},
	}}}
	data, _ := json.Marshal(payload)
	return data
}
func ValidateMetricsURL(endpoint string) error {
	u, err := url.Parse(endpoint)
	if err != nil || u.Host == "" || u.User != nil || u.RawQuery != "" || u.Fragment != "" {
		return fmt.Errorf("OTLP metrics URL must not contain credentials, query parameters or fragments")
	}
	local := u.Hostname() == "localhost" || u.Hostname() == "127.0.0.1" || u.Hostname() == "::1"
	if u.Scheme != "https" && !(u.Scheme == "http" && local) {
		return fmt.Errorf("OTLP metrics require HTTPS except on loopback")
	}
	return nil
}
func ExportMetrics(ctx context.Context, endpoint string) error {
	if err := ValidateMetricsURL(endpoint); err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(MetricsPayload()))
	if err != nil {
		return fmt.Errorf("invalid metrics request")
	}
	req.Header.Set("Content-Type", "application/json")
	client := &http.Client{Timeout: 3 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	response, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("metrics export connection failed")
	}
	defer response.Body.Close()
	io.Copy(io.Discard, io.LimitReader(response.Body, 65536))
	if response.StatusCode != 200 {
		return fmt.Errorf("metrics export returned HTTP %d", response.StatusCode)
	}
	return nil
}
func StartMetrics(ctx context.Context, endpoint string, log *Log) (func(), error) {
	if endpoint == "" {
		return func() {}, nil
	}
	if err := ValidateMetricsURL(endpoint); err != nil {
		return nil, err
	}
	lifetime, cancel := context.WithCancel(ctx)
	done := make(chan struct{})
	go func() {
		defer close(done)
		ticker := time.NewTicker(10 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-lifetime.Done():
				return
			case <-ticker.C:
				if ExportMetrics(lifetime, endpoint) != nil && lifetime.Err() == nil {
					log.Emit("metrics_export_failed")
				}
			}
		}
	}()
	return func() { cancel(); <-done }, nil
}
