package bridge

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"

	"golang.org/x/sys/unix"
)

type Versions struct {
	Pnpm   string `json:"pnpm"`
	Codex  string `json:"codex"`
	Node   string `json:"node"`
	Commit string `json:"commit"`
}
type Config struct {
	Root, Runtime, Data, CodexHome, Socket, Registrations, Node, Codex, Server, Host string
	Port                                                                             int
	Versions                                                                         Versions
}

func LoadConfig(root string) (Config, error) {
	c := Config{Root: root, Host: envDefault("T3_BRIDGE_HOST", "127.0.0.1")}
	home, err := os.UserHomeDir()
	if err != nil {
		return c, err
	}
	c.Data, err = filepath.Abs(envDefault("T3_BRIDGE_HOME", filepath.Join(home, ".local/share/t3-codex-bridge")))
	if err != nil {
		return c, err
	}
	c.CodexHome, err = filepath.Abs(envDefault("CODEX_HOME", filepath.Join(home, ".codex")))
	if err != nil {
		return c, err
	}
	c.Port, err = strconv.Atoi(envDefault("T3_BRIDGE_PORT", "18773"))
	if err != nil || c.Port < 1024 || c.Port > 65535 {
		return c, fmt.Errorf("T3_BRIDGE_PORT must be 1024–65535")
	}
	if c.Host == "" || strings.ContainsAny(c.Host, "/\r\n \t") {
		return c, fmt.Errorf("T3_BRIDGE_HOST must be an IP address or hostname")
	}
	c.Socket = filepath.Join(c.CodexHome, "app-server-control/app-server-control.sock")
	c.Registrations = filepath.Join(c.Data, "registrations")
	c.Runtime = filepath.Join(root, "runtime")
	if _, err = os.Stat(c.Runtime); os.IsNotExist(err) {
		c.Runtime = filepath.Join(root, ".runtime")
	}
	c.Node = filepath.Join(c.Runtime, "node/bin/node")
	if _, err = os.Stat(c.Node); os.IsNotExist(err) {
		c.Node, _ = exec.LookPath("node")
	}
	c.Codex = filepath.Join(c.Runtime, "codex/bin/codex")
	if _, err = os.Stat(c.Codex); os.IsNotExist(err) {
		c.Codex = filepath.Join(c.Runtime, "codex/node_modules/.bin/codex")
	}
	c.Server = filepath.Join(c.Runtime, "t3/apps/server/dist/bin.mjs")
	data, err := os.ReadFile(filepath.Join(root, "versions.json"))
	if err != nil {
		return c, err
	}
	err = json.Unmarshal(data, &c.Versions)
	return c, err
}
func envDefault(key, value string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return value
}
func FindRoot() (string, error) {
	exe, err := os.Executable()
	if err != nil {
		return "", err
	}
	exe, err = filepath.EvalSymlinks(exe)
	if err != nil {
		return "", err
	}
	dir := filepath.Dir(exe)
	for i := 0; i < 3; i++ {
		if _, err := os.Stat(filepath.Join(dir, "versions.json")); err == nil {
			return dir, nil
		}
		dir = filepath.Dir(dir)
	}
	return "", fmt.Errorf("bundle incomplete: versions.json is missing beside the installation")
}
func (c Config) Environment() []string {
	values := map[string]string{}
	for _, e := range os.Environ() {
		k, v, ok := strings.Cut(e, "=")
		if ok {
			values[k] = v
		}
	}
	for _, key := range []string{"VITE_DEV_SERVER_URL", "VITE_HTTP_URL", "VITE_WS_URL", "T3CODE_OTLP_TRACES_URL", "T3CODE_OTLP_METRICS_URL"} {
		delete(values, key)
	}
	for k, v := range map[string]string{
		"CODEX_HOME": c.CodexHome, "T3CODE_HOME": filepath.Join(c.Data, "t3"), "T3_CODEX_BINARY": c.Codex,
		"T3_CODEX_SHARED_SOCKET": c.Socket, "T3_CODEX_SHARED_PROJECTS": "[]", "T3_CODEX_SHARED_REGISTRATIONS": c.Registrations,
		"T3_CODEX_START_DAEMON": "0", "T3_CODEX_MICRO_SOCKET": "", "T3CODE_TAILSCALE_SERVE": "false",
		"T3CODE_TELEMETRY_ENABLED": "false", "T3_BRIDGE_SAFE_LOGS": "1", "T3CODE_TRACE_MIN_LEVEL": "None", "T3CODE_TRACE_TIMING_ENABLED": "false",
		"PATH": filepath.Dir(c.Node) + ":" + filepath.Dir(c.Codex) + ":" + values["PATH"],
	} {
		values[k] = v
	}
	out := make([]string, 0, len(values))
	for k, v := range values {
		out = append(out, k+"="+v)
	}
	return out
}
func RaiseLimit() (uint64, error) {
	var limit unix.Rlimit
	if err := unix.Getrlimit(unix.RLIMIT_NOFILE, &limit); err != nil {
		return 0, err
	}
	if limit.Cur >= 10240 {
		return limit.Cur, nil
	}
	if limit.Max < 10240 {
		return limit.Cur, fmt.Errorf("hard descriptor limit %d is below 10240; no global limit changed", limit.Max)
	}
	limit.Cur = 10240
	if err := unix.Setrlimit(unix.RLIMIT_NOFILE, &limit); err != nil {
		return 0, err
	}
	return limit.Cur, nil
}
func (c Config) Installed() error {
	if filepath.Base(c.Runtime) == ".runtime" {
		data, err := os.ReadFile(filepath.Join(c.Runtime, "installed.json"))
		if err != nil {
			return fmt.Errorf("source runtime has not been built; run bridge setup")
		}
		var stamp struct {
			Versions
			PatchSHA256 string `json:"patchSHA256"`
		}
		if err = json.Unmarshal(data, &stamp); err != nil {
			return fmt.Errorf("invalid source build receipt; run bridge setup")
		}
		patch, err := os.ReadFile(filepath.Join(c.Root, "shared-codex.patch"))
		if err != nil {
			return err
		}
		if stamp.Versions != c.Versions || stamp.PatchSHA256 != fmt.Sprintf("%x", sha256.Sum256(patch)) {
			return fmt.Errorf("source runtime is stale; run bridge setup")
		}
	}

	for _, p := range []string{c.Node, c.Codex, c.Server, filepath.Join(filepath.Dir(c.Server), "client/index.html")} {
		if p == "" {
			return fmt.Errorf("Node runtime missing")
		}
		if _, err := os.Stat(p); err != nil {
			return fmt.Errorf("installation incomplete: %s", p)
		}
	}
	return nil
}
func (c Config) Address() string { return net.JoinHostPort(c.Host, strconv.Itoa(c.Port)) }
