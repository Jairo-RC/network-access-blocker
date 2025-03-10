# network-access-blocker
🔒 Network Access Blocker (ARP Spoofer) - A Python-based tool to block unauthorized devices from a network using ARP spoofing. Features real-time device detection, GUI-based control, and auto router IP detection. Built for ethical security testing and educational purposes. ⚠ Use responsibly. 🚀

⚠ **Legal Notice:** This software is for educational and testing purposes only in controlled environments. We are not responsible for any misuse of this tool.

---

## 📌 Features

✅ Automatically scans the network to list connected devices.  
✅ Intuitive and easy-to-use graphical interface.  
✅ One-click device blocking and unblocking.  
✅ Real-time ARP Spoofing implementation.  

---

## 📦 Installation

### 🔹 Prerequisites
Make sure you have Python 3 installed on your system. You also need to install the following dependencies:

```bash
pip install scapy customtkinter netifaces
```

If you're on **Windows**, also install `Npcap` from [Npcap Official Site](https://nmap.org/npcap/).

---

## 🚀 Usage

1️⃣ **Run the script**

```bash
python bloqueador.py
```

2️⃣ **Select or enter an IP**
- The application will automatically list the connected IPs on the network.  
- You can also manually enter an IP to block.

3️⃣ **Start Blocking**
- Click the **"Start Blocking"** button to disconnect the selected IP.
- The device will lose network access while the script is running.

4️⃣ **Stop Blocking**
- Click **"Stop Blocking"** to restore the device's connection.

---

## 🖥 Screenshots

🚧 *(Coming soon: Add screenshots of the application interface for better clarity.)* 🚧

---

## ⚠ Warning

Using this tool on unauthorized networks is **illegal** and may have serious consequences. Use it only in test environments or with explicit authorization.

---

## 📜 License

This project is distributed under the MIT license. You can modify and share the code for educational and research purposes.

🚀 **Enjoy and experiment responsibly!**
