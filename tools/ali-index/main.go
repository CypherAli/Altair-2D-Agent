// ali-index: quet repo -> JSON [{path,ext,lines,symbols}] (thay scan Python, nhanh 10-50x).
// Chay: ali-index.exe <repo> [max_files] . Stdlib only, khong can go get.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

var skipDirs = map[string]bool{
	".git": true, "target": true, "node_modules": true, ".cache": true,
	"__pycache__": true, ".venv": true, "dist": true, "build": true,
	".next": true, "out": true, "vendor": true, "Pods": true,
	".idea": true, ".vscode": true, "tmp": true, "temp": true, ".tmp": true,
}

var codeExts = map[string]bool{
	".rs": true, ".go": true, ".py": true, ".js": true, ".mjs": true,
	".ts": true, ".tsx": true, ".jsx": true, ".html": true, ".css": true,
	".json": true, ".toml": true, ".md": true,
}

type pattern struct {
	ext string
	re  *regexp.Regexp
}

var patterns = []pattern{
	{".py", regexp.MustCompile(`^\s*(?:def|class)\s+(\w+)`)},
	{".rs", regexp.MustCompile(`^\s*(?:pub\s+)?fn\s+(\w+)`)},
	{".go", regexp.MustCompile(`^\s*func\s+(?:\([^)]*\)\s*)?(\w+)`)},
	{".js", regexp.MustCompile(`^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)`)},
	{".mjs", regexp.MustCompile(`^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)`)},
	{".ts", regexp.MustCompile(`^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)`)},
}

type Entry struct {
	Path    string   `json:"path"`
	Full    string   `json:"full"`
	Ext     string   `json:"ext"`
	Lines   int      `json:"lines"`
	Symbols []string `json:"symbols"`
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: ali-index.exe <repo> [max_files]")
		os.Exit(1)
	}
	root := os.Args[1]
	maxFiles := 300
	if len(os.Args) > 2 {
		if n, err := strconv.Atoi(os.Args[2]); err == nil && n > 0 {
			maxFiles = n
		}
	}
	var out []Entry
	filepath.WalkDir(root, func(p string, d os.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if d.IsDir() {
			if p != root && skipDirs[d.Name()] {
				return filepath.SkipDir
			}
			return nil
		}
		if len(out) >= maxFiles {
			return filepath.SkipAll
		}
		ext := strings.ToLower(filepath.Ext(p))
		if !codeExts[ext] {
			return nil
		}
		info, err := d.Info()
		if err != nil || info.Size() > 120000 {
			return nil
		}
		var re *regexp.Regexp
		for _, pt := range patterns {
			if pt.ext == ext {
				re = pt.re
				break
			}
		}
		var symbols []string
		lines := 0
		f, err := os.Open(p)
		if err != nil {
			return nil
		}
		sc := bufio.NewScanner(f)
		sc.Buffer(make([]byte, 64*1024), 1024*1024)
		for sc.Scan() {
			lines++
			if lines > 2000 {
				break
			}
			if re != nil {
				if m := re.FindStringSubmatch(sc.Text()); m != nil {
					symbols = append(symbols, m[1])
					if len(symbols) >= 40 {
						break
					}
				}
			}
		}
		f.Close()
		rel, err := filepath.Rel(root, p)
		if err != nil {
			rel = p
		}
		out = append(out, Entry{Path: rel, Full: p, Ext: ext, Lines: lines, Symbols: symbols})
		return nil
	})
	if out == nil {
		out = []Entry{}
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(out); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
