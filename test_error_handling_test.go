package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestReadConfig_TableDriven(t *testing.T) {
	tmpDir := t.TempDir()

	validPath := filepath.Join(tmpDir, "valid.json")
	validContent := `{"key":"value","number":42}`
	err := os.WriteFile(validPath, []byte(validContent), 0o644)
	assert.NoError(t, err)

	invalidJSONPath := filepath.Join(tmpDir, "invalid.json")
	invalidContent := `{"key":`
	err = os.WriteFile(invalidJSONPath, []byte(invalidContent), 0o644)
	assert.NoError(t, err)

	nonExistentPath := filepath.Join(tmpDir, "does_not_exist.json")

	tests := []struct {
		name       string
		path       string
		wantNonNil bool
	}{
		{
			name:       "valid JSON file returns non-nil map",
			path:       validPath,
			wantNonNil: true,
		},
		{
			name:       "invalid JSON file still returns map (error ignored)",
			path:       invalidJSONPath,
			wantNonNil: true,
		},
		{
			name:       "non-existent file returns nil map (read error ignored)",
			path:       nonExistentPath,
			wantNonNil: false,
		},
		{
			name:       "empty path returns nil map (read error ignored)",
			path:       "",
			wantNonNil: false,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			got := ReadConfig(tt.path)
			if tt.wantNonNil {
				assert.NotNil(t, got)
			} else {
				assert.Nil(t, got)
			}
		})
	}
}

func TestReadConfig_ContentBehavior(t *testing.T) {
	tmpDir := t.TempDir()

	tests := []struct {
		name         string
		content      string
		expectFields map[string]interface{}
	}{
		{
			name:    "simple string field",
			content: `{"name":"test"}`,
			expectFields: map[string]interface{}{
				"name": "test",
			},
		},
		{
			name:    "multiple fields with number and bool",
			content: `{"name":"multi","count":3,"active":true}`,
			expectFields: map[string]interface{}{
				"name":   "multi",
				"count":  float64(3),
				"active": true,
			},
		},
		{
			name:         "empty JSON object",
			content:      `{}`,
			expectFields: map[string]interface{}{},
		},
	}

	for i, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			path := filepath.Join(tmpDir, "cfg_"+string(rune('a'+i))+".json")
			err := os.WriteFile(path, []byte(tt.content), 0o644)
			assert.NoError(t, err)

			got := ReadConfig(path)
			assert.NotNil(t, got)

			for k, v := range tt.expectFields {
				val, ok := got[k]
				assert.True(t, ok, "expected key %q to exist", k)
				assert.Equal(t, v, val)
			}
		})
	}
}

func TestReadConfig_InvalidJSONResultsInZeroValueMap(t *testing.T) {
	tmpDir := t.TempDir()
	path := filepath.Join(tmpDir, "bad.json")
	err := os.WriteFile(path, []byte(`not-json`), 0o644)
	assert.NoError(t, err)

	got := ReadConfig(path)
	// When json.Unmarshal fails into a nil map, it stays nil
	assert.Nil(t, got)
}

func TestWriteLog_TableDriven(t *testing.T) {
	// Note: WriteLog ignores all errors and does not close the file.
	// We only assert that it does not panic and that the file is created/appended.
	tmpDir := t.TempDir()
	origWD, err := os.Getwd()
	assert.NoError(t, err)

	err = os.Chdir(tmpDir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWD)
	}()

	tests := []struct {
		name    string
		message string
	}{
		{
			name:    "write simple message",
			message: "hello world",
		},
		{
			name:    "write empty message",
			message: "",
		},
		{
			name:    "write multi-line message",
			message: "line1\nline2\nline3",
		},
		{
			name:    "write unicode message",
			message: "こんにちは世界",
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			assert.FileNotExists(t, "app.log")
			WriteLog(tt.message)
			assert.FileExists(t, "app.log")

			data, err := os.ReadFile("app.log")
			assert.NoError(t, err)
			// Because WriteLog opens with O_APPEND|O_CREATE and ignores errors,
			// we only assert that the file is readable and is not nil.
			assert.NotNil(t, data)
		})
	}
}

func TestWriteLog_AppendsToExistingFile(t *testing.T) {
	tmpDir := t.TempDir()
	origWD, err := os.Getwd()
	assert.NoError(t, err)

	err = os.Chdir(tmpDir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWD)
	}()

	initial := "first\n"
	err = os.WriteFile("app.log", []byte(initial), 0o644)
	assert.NoError(t, err)

	WriteLog("second\n")
	data, err := os.ReadFile("app.log")
	assert.NoError(t, err)
	assert.Contains(t, string(data), "first")
	assert.Contains(t, string(data), "second")
}

func TestWriteLog_DoesNotPanicOnReadOnlyDirectory(t *testing.T) {
	// On some systems, making directory read-only may not prevent file creation,
	// but we at least ensure no panic occurs.
	tmpDir := t.TempDir()
	origWD, err := os.Getwd()
	assert.NoError(t, err)

	err = os.Chdir(tmpDir)
	assert.NoError(t, err)
	defer func() {
		_ = os.Chdir(origWD)
	}()

	err = os.Chmod(tmpDir, 0o500)
	assert.NoError(t, err)

	assert.NotPanics(t, func() {
		WriteLog("message in possibly read-only dir")
	})
}

func TestProcessData_TableDriven(t *testing.T) {
	tests := []struct {
		name        string
		input       string
		want        string
		wantPanic   bool
		panicSubstr string
	}{
		{
			name:      "non-empty string returns same string",
			input:     "data",
			want:      "data",
			wantPanic: false,
		},
		{
			name:      "whitespace string is treated as non-empty",
			input:     "   ",
			want:      "   ",
			wantPanic: false,
		},
		{
			name:        "empty string panics",
			input:       "",
			want:        "",
			wantPanic:   true,
			panicSubstr: "empty input",
		},
		{
			name:      "long string returns same string",
			input:     "this is a long string used for testing ProcessData behavior",
			want:      "this is a long string used for testing ProcessData behavior",
			wantPanic: false,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			if tt.wantPanic {
				defer func() {
					r := recover()
					assert.NotNil(t, r, "expected panic but none occurred")
					if r != nil {
						msg, ok := r.(string)
						if ok {
							assert.Contains(t, msg, tt.panicSubstr)
						}
					}
				}()
				_ = ProcessData(tt.input)
				return
			}

			assert.NotPanics(t, func() {
				got := ProcessData(tt.input)
				assert.Equal(t, tt.want, got)
			})
		})
	}
}

func TestProcessData_PanicMessageExact(t *testing.T) {
	defer func() {
		r := recover()
		assert.NotNil(t, r)
		if r != nil {
			msg, ok := r.(string)
			assert.True(t, ok)
			assert.Equal(t, "empty input", msg)
		}
	}()
	_ = ProcessData("")
}

func TestProcessData_IdempotentForSameInput(t *testing.T) {
	inputs := []string{"a", "b", "c", "123", "test"}
	for _, in := range inputs {
		in := in
		t.Run("idempotent_"+in, func(t *testing.T) {
			first := ProcessData(in)
			second := ProcessData(in)
			assert.Equal(t, first, second)
			assert.Equal(t, in, first)
		})
	}
}

func TestReadConfig_WithPreExistingFilePermissions(t *testing.T) {
	tmpDir := t.TempDir()
	path := filepath.Join(tmpDir, "config.json")

	content := map[string]interface{}{
		"enabled": true,
		"level":   "debug",
	}
	raw, err := json.Marshal(content)
	assert.NoError(t, err)

	err = os.WriteFile(path, raw, 0o400)
	assert.NoError(t, err)

	got := ReadConfig(path)
	assert.NotNil(t, got)
	val, ok := got["enabled"]
	assert.True(t, ok)
	assert.Equal(t, true, val)
}

func TestReadConfig_EmptyFile(t *testing.T) {
	tmpDir := t.TempDir()
	path := filepath.Join(tmpDir, "empty.json")
	err := os.WriteFile(path, []byte(""), 0o644)
	assert.NoError(t, err)

	got := ReadConfig(path)
	assert.Nil(t, got)
}
