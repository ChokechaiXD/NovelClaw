package web

import "embed"

// StaticFiles embeds the static assets directory into the Go binary
//
//go:embed static/*
var StaticFiles embed.FS
