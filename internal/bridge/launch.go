package bridge

import (
	"fmt"
	"golang.org/x/sys/unix"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

func LaunchArgs(args []string, cwd string) ([]string, bool) {
	local := strings.Fields("exec e review login logout mcp plugin app-server remote-control app completion update doctor sandbox debug apply a queue archive delete migrate-rollouts unarchive cloud exec-server features help agents")
	values := strings.Fields("-c --config --enable --disable -i --image -m --model --local-provider -p --profile -s --sandbox -C --cd --add-dir -a --ask-for-approval --remote-auth-token-env")
	contains := func(list []string, s string) bool {
		for _, v := range list {
			if v == s {
				return true
			}
		}
		return false
	}
	command := ""
	directory := false
	for i := 0; i < len(args); i++ {
		a := args[i]
		if a == "--" {
			break
		}
		if contains([]string{"--help", "-h", "--version", "-V", "--remote"}, a) || strings.HasPrefix(a, "--remote=") {
			return nil, true
		}
		if a == "--cd" || strings.HasPrefix(a, "--cd=") || strings.HasPrefix(a, "-C") {
			directory = true
		}
		if contains(values, a) {
			i++
			continue
		}
		if !strings.HasPrefix(a, "-") && command == "" {
			command = a
		}
	}
	if contains(local, command) {
		return nil, true
	}
	if directory || command == "resume" || command == "fork" {
		return append([]string{}, args...), false
	}
	return append([]string{"-C", cwd}, args...), false
}

var identity = regexp.MustCompile(`^[a-zA-Z0-9_-]+$`)

func marker(directory, id, suffix, remove string) error {
	if !filepath.IsAbs(directory) || !identity.MatchString(id) {
		return fmt.Errorf("invalid registration directory or native session ID")
	}
	if err := os.MkdirAll(directory, 0700); err != nil {
		return err
	}
	lock, err := os.OpenFile(filepath.Join(directory, ".lock"), os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return err
	}
	defer lock.Close()
	if err = unix.Flock(int(lock.Fd()), unix.LOCK_EX); err != nil {
		return err
	}
	defer unix.Flock(int(lock.Fd()), unix.LOCK_UN)
	path := filepath.Join(directory, id+suffix)
	f, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if err != nil && !os.IsExist(err) {
		return err
	}
	if err == nil {
		if err = f.Close(); err != nil {
			return err
		}
	}
	err = os.Remove(filepath.Join(directory, id+remove))
	if os.IsNotExist(err) {
		return nil
	}
	return err
}
func Register(directory, id string) error { return marker(directory, id, ".thread", ".unshared") }
func Unshare(directory, id string) error  { return marker(directory, id, ".unshared", ".thread") }
