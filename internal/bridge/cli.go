package bridge

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func Main(ctx context.Context, args []string) error {
	if len(args) == 0 || args[0] == "help" || args[0] == "--help" {
		fmt.Println(`T3 Codex Bridge — Go preview
  bridge setup                  Prepare this bundle (source checkout builds T3)
  bridge login                  Authenticate bundled Codex
  bridge daemon-start           Start only if no daemon socket exists
  bridge serve                  Run bundled T3; bounded child recovery
  bridge pair [--tailscale]     Pair T3 using its existing authentication
  bridge codex [args...]        Opt a terminal session into T3
  bridge codex resume <id>      Resume the same native conversation
  bridge codex unshare <id>     Detach sharing, retaining history
  bridge status [--json]        Protocol health; MCP health is separately reported
  bridge doctor [--json]        Installation and protocol diagnostics
  bridge diagnostics collect   Print a safe JSON support report
  bridge logs                   Show bridge metadata logs
  bridge service install|start|stop|uninstall
  bridge capabilities           Show shared-session limitations
No automatic Codex daemon restarts. Micro is not included.`)
		return nil
	}
	root, err := FindRoot()
	if err != nil {
		return err
	}
	c, err := LoadConfig(root)
	if err != nil {
		return err
	}
	command, rest := args[0], args[1:]
	if command == "capabilities" {
		return json.NewEncoder(os.Stdout).Encode(Capabilities())
	}
	if command == "status" || command == "doctor" {
		if len(rest) > 1 || (len(rest) == 1 && rest[0] != "--json") {
			return fmt.Errorf("usage: bridge %s [--json]", command)
		}
		health := c.Health(ctx)
		if c.Installed() != nil {
			health.Status = "unavailable"
			health.Error = "installation_incomplete"
		}
		if len(rest) > 0 {
			if err := json.NewEncoder(os.Stdout).Encode(health); err != nil {
				return err
			}
			if health.Status == "unavailable" {
				return fmt.Errorf("%s", health.Error)
			}
			return nil
		}
		fmt.Printf("Status: %s\nNative protocol: %s\nMCP: %s (verify in a real session)\nFile limit: %d\n", health.Status, health.Protocol, health.MCP, health.FileLimit)
		if health.Error != "" {
			return fmt.Errorf("%s", health.Error)
		}
		return nil
	}
	if command == "diagnostics" && len(rest) == 1 && rest[0] == "collect" {
		return c.Support(ctx, os.Stdout)
	}
	if command == "logs" {
		return c.ReadLogs(os.Stdout)
	}
	if command == "setup" {
		if len(rest) != 0 {
			return fmt.Errorf("setup takes no arguments")
		}
		if filepath.Base(c.Runtime) == ".runtime" {
			if c.Node == "" {
				return fmt.Errorf("source builds require Node 24; prebuilt bundles include it")
			}
			if err := RunChild(ctx, c.Node, []string{filepath.Join(root, "scripts/build-runtime.mjs"), "setup"}, c.Environment(), os.Stdout, os.Stderr); err != nil {
				return err
			}
		}
		if err := c.Installed(); err != nil {
			return err
		}
		if err := os.MkdirAll(c.Registrations, 0700); err != nil {
			return err
		}
		fmt.Println("Ready. Next: bridge login; bridge daemon-start; bridge serve. No background service installed.")
		return nil
	}
	if err := c.Installed(); err != nil {
		return err
	}
	if _, err := RaiseLimit(); err != nil {
		return err
	}
	switch command {
	case "service":
		if len(rest) != 1 {
			return fmt.Errorf("usage: bridge service install|start|stop|uninstall")
		}
		return c.Service(ctx, rest[0])
	case "login":
		return RunChild(ctx, c.Codex, append([]string{"login"}, rest...), c.Environment(), os.Stdout, os.Stderr)
	case "daemon-start":
		if len(rest) != 0 {
			return fmt.Errorf("daemon-start takes no arguments")
		}
		if _, err := os.Lstat(c.Socket); err == nil {
			if c.Health(ctx).Protocol == "connected" {
				fmt.Println("Existing daemon responds; left unchanged. Verify MCP health in a real session.")
				return nil
			}
			return fmt.Errorf("existing socket is unreachable; no restart or socket removal attempted")
		} else if !os.IsNotExist(err) {
			return err
		}
		return RunChild(ctx, c.Codex, []string{"app-server", "daemon", "start"}, c.Environment(), os.Stdout, os.Stderr)
	case "pair":
		opts := append([]string{c.Server, "pair", "--base-dir", filepath.Join(c.Data, "t3")}, rest...)
		tailscale, port := false, false
		for _, a := range rest {
			if a == "--tailscale" {
				tailscale = true
			}
			if strings.HasPrefix(a, "--tailscale-serve-port") {
				port = true
			}
		}
		if tailscale && !port {
			opts = append(opts, "--tailscale-serve-port", "8243")
		}
		return RunChild(ctx, c.Node, opts, c.Environment(), os.Stdout, os.Stderr)
	case "serve", "codex":
		if err := os.MkdirAll(c.Registrations, 0700); err != nil {
			return err
		}
		log, err := NewLog(c.Data)
		if err != nil {
			return err
		}
		defer log.Close()
		stopMetrics, err := StartMetrics(ctx, os.Getenv("T3_BRIDGE_OTLP_METRICS_URL"), log)
		if err != nil {
			return err
		}
		defer stopMetrics()
		if command == "codex" {
			return c.Terminal(ctx, rest, log)
		}
		if len(rest) != 0 {
			return fmt.Errorf("serve takes no arguments; use T3_BRIDGE_HOST and T3_BRIDGE_PORT")
		}
		fmt.Printf("T3 bridge on %s; waiting for native daemon if absent. Ctrl-C stops T3, not Codex.\n", c.Address())
		return c.Serve(ctx, log)
	default:
		return fmt.Errorf("unknown command: %s", command)
	}
}
