package bridge

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/xml"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
)

func (c Config) serviceLabel() string {
	return fmt.Sprintf("io.github.sadhiappan.t3-bridge.%x", sha256.Sum256([]byte(c.Data)))[:48]
}
func (c Config) ServicePlist() []byte {
	var out bytes.Buffer
	out.WriteString(`<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict>`)
	value := func(tag, s string) {
		fmt.Fprintf(&out, "<%s>", tag)
		xml.EscapeText(&out, []byte(s))
		fmt.Fprintf(&out, "</%s>", tag)
	}
	value("key", "Label")
	value("string", c.serviceLabel())
	value("key", "ProgramArguments")
	out.WriteString("<array>")
	value("string", filepath.Join(c.Root, "bin/bridge"))
	value("string", "serve")
	out.WriteString("</array>")
	value("key", "RunAtLoad")
	out.WriteString("<true/>")
	value("key", "KeepAlive")
	out.WriteString("<false/>")
	value("key", "EnvironmentVariables")
	out.WriteString("<dict>")
	env := map[string]string{"PATH": filepath.Dir(c.Node) + ":" + filepath.Dir(c.Codex) + ":" + os.Getenv("PATH"), "CODEX_HOME": c.CodexHome, "T3_BRIDGE_HOME": c.Data, "T3_BRIDGE_HOST": c.Host, "T3_BRIDGE_PORT": fmt.Sprint(c.Port)}
	if endpoint := os.Getenv("T3_BRIDGE_OTLP_METRICS_URL"); endpoint != "" {
		env["T3_BRIDGE_OTLP_METRICS_URL"] = endpoint
	}
	keys := make([]string, 0, len(env))
	for k := range env {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		value("key", k)
		value("string", env[k])
	}
	out.WriteString("</dict></dict></plist>")
	return out.Bytes()
}
func (c Config) Service(ctx context.Context, action string) error {
	home, err := os.UserHomeDir()
	if err != nil {
		return err
	}
	dir := filepath.Join(home, "Library/LaunchAgents")
	path := filepath.Join(dir, c.serviceLabel()+".plist")
	domain := fmt.Sprintf("gui/%d", os.Getuid())
	run := func(args ...string) error {
		cmd := exec.CommandContext(ctx, "/bin/launchctl", args...)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		return cmd.Run()
	}
	switch action {
	case "install":
		if endpoint := os.Getenv("T3_BRIDGE_OTLP_METRICS_URL"); endpoint != "" {
			if err := ValidateMetricsURL(endpoint); err != nil {
				return err
			}
		}
		if err := os.MkdirAll(dir, 0700); err != nil {
			return err
		}
		f, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if err != nil {
			return fmt.Errorf("service file not changed: %w", err)
		}
		_, err = f.Write(c.ServicePlist())
		closeErr := f.Close()
		if err != nil {
			return err
		}
		if closeErr != nil {
			return closeErr
		}
		fmt.Println("Login service installed. Run bridge service start to start it now. Native Codex is never started or restarted by this service.")
		return nil
	case "start":
		return run("bootstrap", domain, path)
	case "stop":
		return run("bootout", domain+"/"+c.serviceLabel())
	case "uninstall":
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		if !bytes.Contains(data, []byte("<string>"+c.serviceLabel()+"</string>")) {
			return fmt.Errorf("service ownership mismatch; file not removed")
		}
		check := exec.CommandContext(ctx, "/bin/launchctl", "print", domain+"/"+c.serviceLabel())
		err = check.Run()
		if err == nil {
			return fmt.Errorf("service is loaded; run bridge service stop before uninstalling")
		}
		var exit *exec.ExitError
		if !errors.As(err, &exit) || exit.ExitCode() != 113 {
			return fmt.Errorf("cannot verify service is unloaded: %w", err)
		}
		return os.Remove(path)
	default:
		return fmt.Errorf("usage: bridge service install|start|stop|uninstall")
	}
}
