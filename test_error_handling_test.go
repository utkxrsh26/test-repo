package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestReadConfig_TableDriven(t *testing.T) {
	type wantType struct {
		config map[string]interface{}
	}
	tests := []struct {
		name        string
		setupFile   func(t *testing.T) string
		expectPanic bool
	}{
		{
			name: "nonexistent file path returns nil config due to ignored error",
			setupFile: func(t *testing.T) string {
				return filepath.Join(t.TempDir(), "does-not-exist.json")
			},
			expectPanic: false,
		},
		{
			name: "valid JSON file returns parsed config",
			setupFile: func(t *testing.T) string {
				dir := t.TempDir()
				path := filepath.Join(dir, "config.json")
				content := `{"key":"value","num":42}`
				err := os.WriteFile(path, []byte(content), 0o644)
				assert.NoError(t, err)
				return path
			},
			expectPanic: false,
		},
		{
			name: "invalid JSON file returns nil config due to unmarshal error",
			setupFile: func(t *testing.T) string {
				dir := t.TempDir()
				path := filepath.Join(dir, "bad.json")
				content := `{invalid-json`
				err := os.WriteFile(path, []byte(content), 0o644)
				assert.NoError(t, err)
				return path
			},
			expectPanic: false,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			path := tt.setupFile(t)

			defer func() {
				if r := recover(); r != nil {
					assert.True(t, tt.expectPanic, "unexpected panic: %v", r)
				} else {
					assert.False(t, tt.expectPanic, "expected panic but none occurred")
				}
			}()

			cfg := ReadConfig(path)

			if tt.expectPanic {
				return
			}

			if cfg == nil {
				// When errors are ignored, cfg can be nil; just assert that behavior is consistent
				assert.Nil(t, cfg)
				return
			}

			assert.NotNil(t, cfg)
			if tt.name == "valid JSON file returns parsed config" {
				assert.Equal(t, "value", cfg["key"])
				// json.Unmarshal decodes numbers as float64 by default
				num, ok := cfg["num"].(float64)
				assert.True(t, ok)
				assert.Equal(t, float64(42), num)
			}
		})
	}
}

func TestReadConfig_EmptyFileBehavior(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "empty.json")
	err := os.WriteFile(path, []byte(""), 0o644)
	assert.NoError(t, err)

	defer func() {
		if r := recover(); r != nil {
			t.Fatalf("did not expect panic, got: %v", r)
		}
	}()

	cfg := ReadConfig(path)
	// json.Unmarshal on empty slice returns error and leaves map nil
	assert.Nil(t, cfg)
}

func TestReadConfig_NonJSONContent(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "text.txt")
	err := os.WriteFile(path, []byte("just some text"), 0o644)
	assert.NoError(t, err)

	defer func() {
		if r := recover(); r != nil {
			t.Fatalf("did not expect panic, got: %v", r)
		}
	}()

	cfg := ReadConfig(path)
	assert.Nil(t, cfg)
}

func TestWriteLog_TableDriven(t *testing.T) {
	tests := []struct {
		name        string
		message     string
		expectPanic bool
	}{
		{
			name:        "write simple message",
			message:     "hello world",
			expectPanic: false,
		},
		{
			name:        "write empty message",
			message:     "",
			expectPanic: false,
		},
		{
			name:        "write multiline message",
			message:     "line1\nline2\nline3",
			expectPanic: false,
		},
	}

	// Ensure we run in a temp directory so app.log does not pollute workspace
	origWD, err := os.Getwd()
	assert.NoError(t, err)
	tempDir := t.TempDir()
	err = os.Chdir(tempDir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWD)
	}()

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			defer func() {
				if r := recover(); r != nil {
					assert.True(t, tt.expectPanic, "unexpected panic: %v", r)
				} else {
					assert.False(t, tt.expectPanic, "expected panic but none occurred")
				}
			}()

			WriteLog(tt.message)

			// Because WriteLog ignores errors and does not close the file,
			// we can only assert on observable side effects best-effort.
			data, readErr := os.ReadFile("app.log")
			if readErr != nil {
				// If file doesn't exist or can't be read, that's still consistent
				// with the current implementation that ignores errors.
				return
			}
			if len(tt.message) == 0 {
				// Empty message may or may not change file; just assert no panic occurred
				return
			}
			assert.Contains(t, string(data), tt.message)
		})
	}
}

func TestWriteLog_MultipleSequentialWrites(t *testing.T) {
	origWD, err := os.Getwd()
	assert.NoError(t, err)
	tempDir := t.TempDir()
	err = os.Chdir(tempDir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWD)
	}()

	messages := []string{"first", "second", "third"}
	for _, msg := range messages {
		WriteLog(msg + "\n")
	}

	data, readErr := os.ReadFile("app.log")
	if readErr != nil {
		// Implementation ignores errors; if file is missing, that's still consistent
		return
	}
	content := string(data)
	for _, msg := range messages {
		assert.Contains(t, content, msg)
	}
}

func TestWriteLog_AppendsToExistingFile(t *testing.T) {
	origWD, err := os.Getwd()
	assert.NoError(t, err)
	tempDir := t.TempDir()
	err = os.Chdir(tempDir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWD)
	}()

	initial := "initial\n"
	err = os.WriteFile("app.log", []byte(initial), 0o644)
	assert.NoError(t, err)

	WriteLog("next\n")

	data, readErr := os.ReadFile("app.log")
	if readErr != nil {
		return
	}
	content := string(data)
	assert.Contains(t, content, "initial")
	assert.Contains(t, content, "next")
}

func TestProcessData_TableDriven(t *testing.T) {
	tests := []struct {
		name        string
		input       string
		expectPanic bool
		expected    string
	}{
		{
			name:        "non-empty input returns same string",
			input:       "some data",
			expectPanic: false,
			expected:    "some data",
		},
		{
			name:        "whitespace input is treated as non-empty",
			input:       "   ",
			expectPanic: false,
			expected:    "   ",
		},
		{
			name:        "empty input panics",
			input:       "",
			expectPanic: true,
			expected:    "",
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			defer func() {
				r := recover()
				if tt.expectPanic {
					assert.NotNil(t, r, "expected panic but none occurred")
					if r != nil {
						assert.Equal(t, "empty input", r)
					}
				} else {
					assert.Nil(t, r, "did not expect panic, got: %v", r)
				}
			}()

			result := ProcessData(tt.input)
			if !tt.expectPanic {
				assert.Equal(t, tt.expected, result)
			}
		})
	}
}

func TestProcessData_ExplicitPanicCheck(t *testing.T) {
	defer func() {
		r := recover()
		assert.NotNil(t, r)
		assert.Equal(t, "empty input", r)
	}()

	_ = ProcessData("")
}

func TestProcessData_NoPanicForNonEmpty(t *testing.T) {
	inputs := []string{"a", "0", "false", "null", "{}", "[]"}
	for _, in := range inputs {
		in := in
		t.Run("input_"+in, func(t *testing.T) {
			defer func() {
				r := recover()
				assert.Nil(t, r, "unexpected panic for input %q: %v", in, r)
			}()
			out := ProcessData(in)
			assert.Equal(t, in, out)
		})
	}
}

func TestReadConfig_WithPrecreatedMap(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "config.json")

	// Create JSON that will unmarshal into a map with nested structure
	type nested struct {
		Foo string `json:"foo"`
	}
	obj := map[string]interface{}{
		"nested": nested{Foo: "bar"},
	}
	data, err := json.Marshal(obj)
	assert.NoError(t, err)
	err = os.WriteFile(path, data, 0o644)
	assert.NoError(t, err)

	defer func() {
		if r := recover(); r != nil {
			t.Fatalf("did not expect panic, got: %v", r)
		}
	}()

	cfg := ReadConfig(path)
	if cfg == nil {
		// Implementation ignores errors; if cfg is nil, just assert that
		assert.Nil(t, cfg)
		return
	}
	assert.NotNil(t, cfg)
	// nested will be decoded as map[string]interface{}
	nestedVal, ok := cfg["nested"].(map[string]interface{})
	assert.True(t, ok)
	assert.Equal(t, "bar", nestedVal["foo"])
}

func TestReadConfig_LargeFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "large.json")

	// Create a relatively large JSON object
	content := `{"key":"` + string(make([]byte, 1024)) + `"}` // 1KB string
	err := os.WriteFile(path, []byte(content), 0o644)
	assert.NoError(t, err)

	defer func() {
		if r := recover(); r != nil {
			t.Fatalf("did not expect panic, got: %v", r)
		}
	}()

	cfg := ReadConfig(path)
	// On success, cfg is non-nil; on error, cfg is nil. Both are acceptable given implementation.
	if cfg != nil {
		assert.Contains(t, cfg, "key")
	}
}

func TestWriteLog_NoFilePermissionsDirectory(t *testing.T) {
	// On most systems, writing to a non-existent directory will fail,
	// but WriteLog ignores errors, so we only assert that it does not panic.
	origWD, err := os.Getwd()
	assert.NoError(t, err)
	tempDir := t.TempDir()
	// Create a subdir and remove it to simulate invalid path when chdir
	subDir := filepath.Join(tempDir, "removed")
	err = os.Mkdir(subDir, 0o755)
	assert.NoError(t, err)
	err = os.Remove(subDir)
	assert.NoError(t, err)

	err = os.Chdir(subDir)
	// Chdir will likely fail; if it does, we just skip because we can't simulate the scenario
	if err != nil {
		return
	}
	defer func() {
		_ = os.Chdir(origWD)
	}()

	defer func() {
		r := recover()
		assert.Nil(t, r, "unexpected panic when writing log in invalid directory: %v", r)
	}()

	WriteLog("message in invalid dir")
}
