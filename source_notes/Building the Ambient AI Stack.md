# Building the Ambient AI Stack
This guide will walk you through deploying your hyper-contextual AI stack. We use Docker to keep everything containerised and easy to manage. This setup builds the sensory network and the memory backend.
We will deploy Home Assistant (HA) for device management, InfluxDB for long-term memory, Node-RED for complex logic, Mosquitto for custom data streams, and Ollama for the local AI brain.
## 1. The Core Infrastructure
First, install Docker and Docker Compose on your server. Create a new directory named apollo-stack and create a file inside it called docker-compose.yml.
Paste the following configuration into that file. This script pulls down all the necessary operating systems and links them together on a shared virtual network.
```yaml
version: '3.8'
services:
  homeassistant:
    container_name: homeassistant
    image: "ghcr.io/home-assistant/home-assistant:stable"
    volumes:
      - ./ha_config:/config
      - /etc/localtime:/etc/localtime:ro
    restart: unless-stopped
    network_mode: host

  mosquitto:
    container_name: mosquitto
    image: eclipse-mosquitto
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./mosquitto/config:/mosquitto/config
      - ./mosquitto/data:/mosquitto/data
    restart: unless-stopped

  influxdb:
    container_name: influxdb
    image: influxdb:latest
    ports:
      - "8086:8086"
    volumes:
      - ./influxdb:/var/lib/influxdb2
    restart: unless-stopped

  nodered:
    container_name: nodered
    image: nodered/node-red:latest
    ports:
      - "1880:1880"
    volumes:
      - ./nodered:/data
    restart: unless-stopped

  ollama:
    container_name: ollama
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ./ollama:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped

```
## 2. Booting Up and Configuring
Open your terminal, navigate to your apollo-stack folder, and run docker-compose up -d. This command downloads the images and starts your system in the background.
Once running, you need to connect Home Assistant to InfluxDB. Open Home Assistant via your browser and configure the InfluxDB integration. This step ensures every light toggle, sleep metric, and temperature change gets permanently recorded for future causal analysis.
Next, open the Ollama container terminal and run ollama run llama3.2 (or your preferred model). This downloads the weights to your local machine. Your desktop tower's GPU will handle the processing, keeping your data entirely private.
## 3. Piping in "Weird" Data Streams
You will inevitably find data sources that Home Assistant doesn't natively support. Maybe it's a custom biomedical sensor you built for uni, or a bizarre web scraping script. To get this data into your system, you use **MQTT**.
Think of MQTT as a universal message board. The Mosquitto container you spun up acts as the server for this board.
To pipe in custom data, you simply write a tiny script in Python or Node.js. This script reads your weird sensor or API and "publishes" a message to a specific topic on your MQTT board.
### Example: A Custom Python Scraper
Imagine you wrote a script to check your uni portal for new assignments. You can use the paho-mqtt library in Python to send that data straight to your system.
```python
import paho.mqtt.client as mqtt
import json

# Your custom logic here
new_assignments = {"subject": "Biomedical Engineering", "due_date": "15/05/2026"}

client = mqtt.Client()
client.connect("YOUR_SERVER_IP", 1883, 60)

# Publish the data as a JSON string to a specific topic
client.publish("apollo/uni/assignments", json.dumps(new_assignments))
client.disconnect()

```
Home Assistant constantly listens to this MQTT board. You just tell it to watch the apollo/uni/assignments topic. Whenever your script publishes a new message, Home Assistant instantly updates its internal state. The AI brain can then read this state and notify you on your Z Fold if something urgent pops up.

### ADDITIONAL GUI components
To get the visibility and manual control you are looking for, you'll want to swap a few hidden backend components for tools that prioritise their web interfaces.
#### ​1. Visualising the Vector Database
​Instead of letting the AI use a hidden local file for its embeddings, point it to Qdrant.
It's an open-source vector database built in Rust, and it comes with an exceptional built-in Web UI accessible at http://localhost:6333/dashboard. You can browse every single memory the AI has stored. It lets you view the raw text of the memory alongside its numerical vector. You can manually delete bad memories, edit the metadata, or run manual search queries to see exactly what the AI retrieves when it thinks about a specific topic.
#### ​2. Browsing and Editing Automations
​Node-RED is exactly what you need for this. We included it in the initial blueprint, but it's worth highlighting that it is entirely visual.
You open its dashboard in your browser and literally drag and drop connection wires between your data streams and your AI. If you want the AI to only trigger the bedroom lights when your Z Fold 7 is plugged in, you draw a wire connecting the HA phone-charger node to an IF-statement node, then route that to the AI node. It makes complex logic instantly readable.
#### ​3. Managing Logs and Live Data
​To watch the raw "firehose" of data and see what the AI is actively doing, use a two-pronged approach.
First, spin up Dozzle. It's a zero-configuration web interface that taps into Docker. It gives you a clean dashboard to watch the live terminal outputs of your AI models and sensor scrapers in real-time. Second, use Grafana. You connect it to your InfluxDB database. You can build visual dashboards showing your sleep metrics overlaid with your solar power usage, allowing you to manually spot correlations before the AI even does.
#### ​4. Editing Distilled Facts and Connections
​Don't use a database GUI for the high-level semantic facts. Use Obsidian.
Configure your AI agent to write its "distilled facts" and summaries as markdown files directly into an Obsidian vault synced to your desktop. Obsidian's Graph View is the ultimate way to visualise connections. You'll see a web of nodes connecting "Sleep Quality" to "Oatmilk". Because they are just text files, you can manually type in new rules, fix the AI's logic, or link two concepts together yourself. The AI reads those files on its next cycle and instantly learns your manual corrections.

```yaml
# Add these services to your existing docker-compose.yml

  # Qdrant: Replaces the default SQLite vector store with a visual one
  qdrant:
    container_name: qdrant
    image: qdrant/qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - ./qdrant_data:/qdrant/storage
    restart: unless-stopped

  # Dozzle: Real-time visual log viewer for all your containers
  dozzle:
    container_name: dozzle
    image: amir20/dozzle:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "8080:8080"
    restart: unless-stopped

  # Grafana: Visualise the InfluxDB sensor data
  grafana:
    container_name: grafana
    image: grafana/grafana-oss:latest
    ports:
      - "3000:3000"
    volumes:
      - ./grafana:/var/lib/grafana
    restart: unless-stopped

```

### DevOps Agent Supervisor
​To achieve this, we use a framework originally designed for autonomous software engineering and adapt it to manage your server infrastructure. Here is how you build that self-improving, auto-healing loop.
#### ​1. The Meta-Agent Engine
​You need an agent specifically trained for coding and terminal execution. OpenHands (formerly OpenDevin) is the current open-source standard for this.
​You deploy OpenHands as its own Docker container alongside your stack. You point its "brain" to a coding-focused model running on your Ollama instance, like Qwen2.5-Coder. This gives it the ability to write Python scripts, edit YAML files, and understand system logs.
#### ​2. Granting "God Mode" (The Docker Socket)
​For an AI to install new components, it needs permission to alter the host operating system. You achieve this by mounting the host's Docker socket (`/var/run/docker.sock`) directly into the OpenHands container.
​When you ask it to "connect my new smart home device," the agent searches the web for the device's API documentation. It then opens your docker-compose.yml file, writes the configuration for the new integration, and executes docker-compose up -d via its internal terminal. Because it has socket access, that command physically spins up the new container on your desktop tower.
#### ​3. The GitOps Safety Net
​Giving an AI root access to your server is risky. It will inevitably break things. You manage this risk using strict GitOps principles.
​Turn your entire apollo-stack directory into a Git repository. You then give the OpenHands agent a rigid set of system prompts:
​Never edit live files directly.
​Always create a new Git branch (e.g., feature-add-new-sensor).
​Make the changes to the compose file or Python scripts and commit them.
​Execute the deployment.
#### ​4. Automated Rollbacks
​The agent must test its own work. After spinning up a new container, it needs to check the Dozzle logs or ping the new service's port.
​If the new container repeatedly crashes or throws errors, the agent identifies the failure. It then automatically runs git reset --hard HEAD~1 (reverting to the last known good configuration) and restarts the stack. It will then leave a markdown note in your Obsidian vault explaining what failed and why it abandoned the update.
​This setup effectively gives you a junior sysadmin. You just tell it what end result you want, and it handles the messy configuration files and network bridges.
```yaml
# Add this to your docker-compose.yml to give the AI control over the host
  
  openhands:
    container_name: meta_agent
    image: docker.all-hands.dev/all-hands-ai/openhands:main
    ports:
      - "3001:3000"
    environment:
      - WORKSPACE_BASE=/workspace
      - LLM_API_KEY=ollama # Tell it to use your local Ollama instance
      - LLM_BASE_URL=http://host.docker.internal:11434
    volumes:
      # This gives the agent access to your compose files and scripts
      - ./:/workspace
      # CRITICAL: This gives the agent permission to start/stop other containers
      - /var/run/docker.sock:/var/run/docker.sock
    restart: unless-stopped

```
