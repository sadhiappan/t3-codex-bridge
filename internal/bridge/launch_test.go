package bridge

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestLaunchArguments(t *testing.T) {
	for _, tt := range []struct {
		args, want []string
		local      bool
	}{
		{[]string{}, []string{"-C", "/project"}, false},
		{[]string{"--profile", "yolo"}, []string{"-C", "/project", "--profile", "yolo"}, false},
		{[]string{"--model", "m", "exec", "hello"}, nil, true},
		{[]string{"resume", "id"}, []string{"resume", "id"}, false},
		{[]string{"--remote=unix:///a"}, nil, true},
		{[]string{"--", "--remote"}, []string{"-C", "/project", "--", "--remote"}, false},
		{[]string{"-C/other"}, []string{"-C/other"}, false},
	} {
		got, local := LaunchArgs(tt.args, "/project")
		if local != tt.local || !reflect.DeepEqual(got, tt.want) {
			t.Fatalf("%v: got %v %v", tt.args, got, local)
		}
	}
}
func TestRegistration(t *testing.T) {
	dir := t.TempDir()
	if err := Register(dir, "abc"); err != nil {
		t.Fatal(err)
	}
	if err := Unshare(dir, "abc"); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(dir, "abc.thread")); !os.IsNotExist(err) {
		t.Fatal("marker retained")
	}
	if err := Register(dir, "abc"); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(dir, "abc.unshared")); !os.IsNotExist(err) {
		t.Fatal("tombstone retained")
	}
	for _, id := range []string{"../escape", "", "a/b"} {
		if Register(dir, id) == nil {
			t.Fatal("accepted invalid ID")
		}
	}
	info, err := os.Stat(filepath.Join(dir, "abc.thread"))
	if err != nil || info.Mode().Perm() != 0600 {
		t.Fatal("marker permissions")
	}
}
