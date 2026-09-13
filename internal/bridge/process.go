package bridge

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"sync"
	"syscall"
	"time"

	"golang.org/x/term"
)

func RunChild(ctx context.Context, binary string, args, env []string, stdout, stderr io.Writer) error {
	cmd := exec.Command(binary, args...)
	cmd.Env = env
	cmd.Stdin = os.Stdin
	cmd.Stdout = stdout
	cmd.Stderr = stderr
	if err := cmd.Start(); err != nil {
		return err
	}
	signals := make(chan os.Signal, 4)
	signal.Notify(signals, syscall.SIGTERM, syscall.SIGHUP, os.Interrupt)
	defer signal.Stop(signals)
	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()
	for {
		select {
		case err := <-done:
			return err
		case sig := <-signals:
			if sig == os.Interrupt {
				continue
			}
			if err := cmd.Process.Signal(sig); err != nil && !errors.Is(err, os.ErrProcessDone) {
				return err
			}
		case <-ctx.Done():
			_ = cmd.Process.Signal(syscall.SIGTERM)
			select {
			case err := <-done:
				return err
			case <-time.After(5 * time.Second):
				_ = cmd.Process.Kill()
				return <-done
			}
		}
	}
}
func (c Config) Terminal(ctx context.Context, args []string, log *Log) error {
	if len(args) > 0 && args[0] == "unshare" {
		if len(args) != 2 {
			return fmt.Errorf("usage: bridge codex unshare <session-id>")
		}
		if err := Unshare(c.Registrations, args[1]); err != nil {
			return err
		}
		fmt.Println("Sharing disabled; history retained. T3 detaches on its next discovery sweep.")
		return nil
	}
	cwd, err := os.Getwd()
	if err != nil {
		return err
	}
	launch, local := LaunchArgs(args, cwd)
	if local || !term.IsTerminal(int(os.Stdin.Fd())) || !term.IsTerminal(int(os.Stdout.Fd())) {
		return RunChild(ctx, c.Codex, args, c.Environment(), os.Stdout, os.Stderr)
	}
	var mu sync.Mutex
	pending := map[string]bool{}
	latest := ""
	relay, err := StartRelay(ctx, c.Socket, func(id string) { mu.Lock(); pending[id] = true; latest = id; mu.Unlock() }, log.Emit)
	if err != nil {
		return err
	}
	registrationCtx, stop := context.WithCancel(ctx)
	defer stop()
	done := make(chan struct{})
	go func() {
		defer close(done)
		ticker := time.NewTicker(250 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-registrationCtx.Done():
				return
			case <-ticker.C:
				mu.Lock()
				ids := make([]string, 0, len(pending))
				for id := range pending {
					ids = append(ids, id)
				}
				mu.Unlock()
				for _, id := range ids {
					if Register(c.Registrations, id) != nil {
						log.Emit("registration_failed")
						continue
					}
					mu.Lock()
					delete(pending, id)
					mu.Unlock()
					log.EmitSession("session_registered", id)
				}
			}
		}
	}()
	log.Emit("terminal_started")
	err = RunChild(ctx, c.Codex, append([]string{"--remote", "unix://" + relay.Socket, "--no-alt-screen"}, launch...), c.Environment(), os.Stdout, os.Stderr)
	closeErr := relay.Close()
	stop()
	<-done
	mu.Lock()
	defer mu.Unlock()
	for id := range pending {
		if registrationErr := Register(c.Registrations, id); registrationErr != nil {
			log.Emit("registration_failed")
			if err == nil {
				err = registrationErr
			}
		}
	}
	if latest != "" {
		fmt.Fprintf(os.Stderr, "\nResume: bridge codex resume %s\n", latest)
	}
	log.Emit("terminal_stopped")
	if err != nil {
		return err
	}
	return closeErr
}
func (c Config) Serve(ctx context.Context, log *Log) error {
	if err := os.MkdirAll(c.Data, 0700); err != nil {
		return err
	}
	lock, err := os.OpenFile(filepath.Join(c.Data, "serve.lock"), os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return err
	}
	defer lock.Close()
	if err = syscall.Flock(int(lock.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		return fmt.Errorf("another bridge server owns this data directory")
	}
	defer syscall.Flock(int(lock.Fd()), syscall.LOCK_UN)
	// Child output may contain prompts or credentials. It is never copied into diagnostic logs.
	restarts := []time.Time{}
	for {
		if ctx.Err() != nil {
			return nil
		}
		health := c.Health(ctx)
		if health.Protocol != "connected" {
			log.Emit("waiting_for_daemon")
			select {
			case <-ctx.Done():
				return nil
			case <-time.After(5 * time.Second):
				continue
			}
		}
		log.Emit("t3_started")
		err = RunChild(ctx, c.Node, []string{c.Server, "serve", "--base-dir", filepath.Join(c.Data, "t3"), "--host", c.Host, "--port", fmt.Sprint(c.Port), "--no-browser"}, c.Environment(), os.Stdout, os.Stderr)
		if ctx.Err() != nil {
			return nil
		}
		log.Emit("t3_exited")
		now := time.Now()
		kept := restarts[:0]
		for _, at := range restarts {
			if now.Sub(at) < 10*time.Minute {
				kept = append(kept, at)
			}
		}
		restarts = kept
		if len(restarts) >= 3 {
			log.Emit("t3_restart_budget_exhausted")
			return fmt.Errorf("T3 failed repeatedly; automatic recovery stopped. Run bridge doctor")
		}
		restarts = append(restarts, now)
		log.Emit("t3_restart_scheduled")
		select {
		case <-ctx.Done():
			return nil
		case <-time.After(time.Duration(len(restarts)) * time.Second):
		}
	}
}
