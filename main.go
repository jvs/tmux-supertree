package main

import (
	"flag"
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"
)

func main() {
	commandFile := flag.String("command-file", "", "write add-window command here instead of running it")
	returnCommand := flag.String("return-command", "", "append this to the command file after add-window")
	switchCommand := flag.String("switch-command", "", "write this command to the command file when switching to another tool")
	searchMode := flag.Bool("search-mode", false, "start with search focused")
	flag.Parse()

	initialSessID, initialWinID, err := getCurrentSessionAndWindow()
	if err != nil {
		fmt.Fprintf(os.Stderr, "tmux-supertree: %v\n", err)
		os.Exit(1)
	}

	m := newModel(initialSessID, initialWinID, *commandFile, *returnCommand, *switchCommand, *searchMode)
	p := tea.NewProgram(m, tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "tmux-supertree: %v\n", err)
		os.Exit(1)
	}
}
