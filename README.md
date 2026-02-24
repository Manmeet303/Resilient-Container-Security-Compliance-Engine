# **🛡️ Resilient Container Security & Compliance Engine**

An Advanced Operating Systems Project: A distributed systems approach to automated threat detection, fault tolerance, and efficient data partitioning for containerized environments.

## **📖 Project Overview**

Modern container security tools (like Trivy or Clair) are incredibly effective but are traditionally deployed as monolithic blockers in CI/CD pipelines or as heavy, CPU-intensive daemons on host servers.

The **Resilient Container Security & Compliance Engine** solves this by decoupling the scanning process into a custom-built, three-pillar distributed system. It actively monitors Docker events in real-time, offloads heavy vulnerability scans to a fault-tolerant worker cluster, and uses a cryptographic distributed cache to ensure identical image layers are never scanned twice. Furthermore, it shifts security from *passive logging* to *active resilience* by automatically spinning up failover replicas if a monitored container crashes.

## **🏗️ System Architecture**

Our architecture is divided into three distinct, distributed pillars to ensure no single point of failure (SPOF) and optimal resource allocation:

### **1\. The Control Plane (Master Node)**

* **Role:** The Brain.  
* **Function:** Hooks into the Docker Engine API via socket to listen for container\_start and container\_die events. It pushes state updates to a real-time WebSocket dashboard and executes the **Auto-Failover** logic (instantly spinning up replicas when critical containers fail).

### **2\. Distributed Task Scheduler (Worker Nodes)**

* **Role:** The Muscle.  
* **Function:** A distributed pool of worker nodes that pull CVE scan jobs from the Master's in-memory queue via **gRPC**.  
* **Fault Tolerance:** Implements a strict 5-second **Heartbeat Protocol**. If a worker crashes mid-scan, the Master reclaims the job and reassigns it to a healthy node.

### **3\. Distributed Cache (Cache Nodes)**

* **Role:** The Memory.  
* **Function:** Worker nodes extract the SHA-256 hashes of container image layers before scanning. They query the cache via **Consistent Hashing** to see if the layer was recently scanned.  
* **Optimization:** Bypasses Trivy scanning on Cache Hits. Uses a custom **LRU (Least Recently Used)** eviction policy to manage memory constraints.

## **⚙️ Core Tech Stack**

* **Language:** Python (and/or GoLang)  
* **Container Control:** Docker Engine API (docker-py)  
* **Security Scanner:** [Trivy](https://github.com/aquasecurity/trivy) (Aqua Security)  
* **Communication:** gRPC & Protocol Buffers  
* **Backend API:** FastAPI  
* **Frontend UI:** HTML/CSS/JS with WebSockets for real-time, bi-directional updates.

## **👥 Team Members & Division of Labor**

This project is developed for the Advanced Operating Systems curriculum. The architecture has been divided into distinct modules for clear ownership:

| Team Member | Module Ownership | Key Responsibilities |
| :---- | :---- | :---- |
| **Mahip** | **Control Plane & Resilience** | Docker Socket API Integration, Auto-Failover Logic, FastAPI backend, and the Real-time Web Dashboard UI. |
| **Margesh** | **Distributed Task Scheduler** | In-Memory Job Queue, gRPC Worker Node deployment, Trivy execution, and the Heartbeat Fault-Tolerance Protocol. |
| **Manmeet** | **Distributed Cache** | SHA-256 Layer Hashing extraction, Consistent Hashing routing algorithm, and LRU Cache Eviction logic. |

## **🚀 Key Features**

* \[x\] **Zero-Blocking Deployments:** Scan jobs are queued asynchronously; containers boot instantly without waiting for security clearance.  
* \[x\] **Active Auto-Failover:** Sub-second recovery (replica spin-up) if a monitored application container dies.  
* \[x\] **Cryptographic Optimization:** Projected 80% reduction in CPU overhead by caching standard base image layers (e.g., Ubuntu, Alpine).  
* \[x\] **Chaos-Resistant:** Worker nodes can be randomly terminated without losing scan jobs, thanks to the Master's heartbeat monitor.  
* \[x\] **Real-Time Visibility:** WebSocket-driven dashboard requires zero manual page refreshes.

## **🧪 Experimental Setup (Chaos Engineering)**

To validate our distributed concepts, the system will be tested on a simulated 4-node cluster (1 Master, 2 Workers, 1 Cache). We will execute "Chaos Engineering" scenarios, including:

1. Deploying intentionally vulnerable (deprecated) Nginx images to trigger CVE alerts.  
2. Manually killing Worker terminal processes mid-scan to verify heartbeat reassignment.  
3. Force-stopping critical containers to measure the millisecond latency of the auto-failover replication.

## **🛠️ Getting Started (Development)**

*(Instructions will be updated as the codebase is initialized)*

1. Clone the repository:  
   git clone \[https://github.com/your-org/resilient-container-security.git\](https://github.com/your-org/resilient-container-security.git)

2. Ensure Docker daemon is running and accessible.  
3. Install dependencies:  
   pip install \-r requirements.txt

4. Start the Master Node Control Plane:  
   python master\_node.py

5. Start Worker Nodes:  
   python worker\_node.py

*Built for Advanced Operating Systems*