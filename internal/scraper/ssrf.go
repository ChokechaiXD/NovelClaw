package scraper

import (
	"fmt"
	"net"
	"net/url"
	"strings"
	"syscall"
)

// validatePublicURL blocks requests to non-HTTP(S) schemes and private /
// loopback / link-local addresses (SSRF guard). The server accepts arbitrary
// URLs from API clients, so we must never fetch internal hosts.
func validatePublicURL(rawURL string) error {
	u, err := url.Parse(strings.TrimSpace(rawURL))
	if err != nil {
		return fmt.Errorf("invalid url: %w", err)
	}
	if u.Scheme != "http" && u.Scheme != "https" {
		return fmt.Errorf("unsupported url scheme: %q (only http/https allowed)", u.Scheme)
	}
	host := u.Hostname()
	if host == "" {
		return fmt.Errorf("url has no host: %s", rawURL)
	}

	var ips []net.IP
	if ip := net.ParseIP(host); ip != nil {
		ips = []net.IP{ip}
	} else {
		resolved, err := net.LookupIP(host)
		if err != nil {
			return fmt.Errorf("cannot resolve host %q: %w", host, err)
		}
		ips = resolved
	}

	for _, ip := range ips {
		if isDisallowedIP(ip) {
			return fmt.Errorf("url host %q resolves to a private/reserved address (%s); blocked", host, ip)
		}
	}
	return nil
}

// validateDial is an http.Dialer Control hook: the connection target has
// already been resolved, so re-checking it here closes the DNS-rebinding
// window between URL validation and the actual dial.
func validateDial(network, address string, conn syscall.RawConn) error {
	host, _, err := net.SplitHostPort(address)
	if err != nil {
		return err
	}
	ip := net.ParseIP(host)
	if ip == nil {
		return fmt.Errorf("non-IP dial target %q blocked", host)
	}
	if isDisallowedIP(ip) {
		return fmt.Errorf("dial to private/reserved address %s blocked (SSRF)", ip)
	}
	return nil
}

func isDisallowedIP(ip net.IP) bool {
	if ip4 := ip.To4(); ip4 != nil {
		ip = ip4
	}
	return ip.IsLoopback() || ip.IsPrivate() || ip.IsLinkLocalUnicast() ||
		ip.IsLinkLocalMulticast() || ip.IsInterfaceLocalMulticast() ||
		ip.IsMulticast() || ip.IsUnspecified()
}
