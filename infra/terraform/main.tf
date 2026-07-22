terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Variables
variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "The region to deploy resources to (us-central1 is free-tier eligible)"
}

variable "zone" {
  type        = string
  default     = "us-central1-a"
  description = "The zone for the GCE Instance"
}

# 1. Pub/Sub Topic for Honeypot Logs
resource "google_pubsub_topic" "honeypot_events" {
  name = "cowrie-events"
}

# 2. Cloud Logging Router Sink
# Forwards Cowrie events from Cloud Logging to the Pub/Sub topic
resource "google_logging_project_sink" "cowrie_logs_sink" {
  name                   = "cowrie-logs-sink"
  destination            = "pubsub.googleapis.com/${google_pubsub_topic.honeypot_events.id}"
  filter                 = "logName:\"logs/cowrie_log\" AND jsonPayload.eventid:*"
  unique_writer_identity = true
}

# Give permission to Logging sink service account to publish to Pub/Sub
resource "google_pubsub_topic_iam_binding" "pubsub_publisher" {
  topic = google_pubsub_topic.honeypot_events.name
  role  = "roles/pubsub.publisher"
  members = [
    google_logging_project_sink.cowrie_logs_sink.writer_identity,
  ]
}

# 3. Firestore Database
resource "google_firestore_database" "firestore_db" {
  name        = "(default)"
  location_id = "nam5" # Multi-region US (free-tier eligible)
  type        = "FIRESTORE_NATIVE"
}

# 4. Secret Manager for API Keys
resource "google_secret_manager_secret" "virustotal_key" {
  secret_id = "virustotal-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "gemini_key" {
  secret_id = "gemini-api-key"
  replication {
    auto {}
  }
}

# 5. Service Account for Cloud Function
resource "google_service_account" "triage_function_sa" {
  account_id   = "triage-function-sa"
  display_name = "AI Triage Cloud Function Service Account"
}

# Grant access to Firestore and Secret Manager
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.triage_function_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "vt_secret_access" {
  secret_id = google_secret_manager_secret.virustotal_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.triage_function_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "gemini_secret_access" {
  secret_id = google_secret_manager_secret.gemini_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.triage_function_sa.email}"
}

# 6. Honeypot VM (e2-micro - Always Free Tier VM)
resource "google_compute_address" "honeypot_ip" {
  name   = "honeypot-static-ip"
  region = var.region
}

resource "google_compute_instance" "honeypot_vm" {
  name         = "cowrie-honeypot"
  machine_type = "e2-micro"
  zone         = var.zone

  tags = ["honeypot", "ssh-admin"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
      size  = 20 # 20GB is within the 30GB free limit
    }
  }

  network_interface {
    network = "default"
    access_config {
      nat_ip = google_compute_address.honeypot_ip.address
    }
  }

  service_account {
    scopes = ["https://www.googleapis.com/auth/logging.write", "https://www.googleapis.com/auth/monitoring.write"]
  }

  metadata_startup_script = <<-EOT
    #!/bin/bash
    set -e

    # 1. Update and install packages
    apt-get update -y
    apt-get install -y git python3-virtualenv libssl-dev libffi-dev build-essential libpython3-dev iptables curl

    # 2. Configure Host SSH to listen on 22022 for management
    sed -i 's/#Port 22/Port 22022/' /etc/ssh/sshd_config
    systemctl restart sshd

    # 3. Create Cowrie user
    if ! id -u cowrie >/dev/null 2>&1; then
      useradd -m -s /bin/bash cowrie
    fi

    # 4. Install and configure Cowrie
    cd /home/cowrie
    if [ ! -d "cowrie" ]; then
      sudo -u cowrie git clone https://github.com/cowrie/cowrie.git
    fi
    cd cowrie
    sudo -u cowrie python3 -m venv cowrie-env
    sudo -u cowrie ./cowrie-env/bin/pip install --upgrade pip
    sudo -u cowrie ./cowrie-env/bin/pip install -r requirements.txt

    # Create local configuration file
    cat << 'EOF' > /home/cowrie/cowrie/etc/cowrie.cfg
    [core]
    hostname = srv-prod-web-01

    [ssh]
    enabled = true
    listen_endpoints = tcp:2222:interface=0.0.0.0

    [telnet]
    enabled = false

    [output_jsonlog]
    enabled = true
    logfile = var/log/cowrie/cowrie.json
    epoch_timestamps = false
    format = json
    EOF

    # Start Cowrie
    sudo -u cowrie ./bin/cowrie start

    # 5. Forward port 22 (SSH) to 2222 (Honeypot)
    iptables -t nat -A PREROUTING -p tcp --dport 22 -j REDIRECT --to-port 2222
    # Make iptables persistent
    apt-get install -y iptables-persistent
    iptables-save > /etc/iptables/rules.v4

    # 6. Install Google Cloud Ops Agent
    curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
    bash add-google-cloud-ops-agent-repo.sh --also-install

    # Configure Ops Agent
    cat << 'EOF' > /etc/google-cloud-ops-agent/config.yaml
    logging:
      receivers:
        cowrie_log:
          type: files
          include_paths:
            - /home/cowrie/cowrie/var/log/cowrie/cowrie.json
      processors:
        parse_json:
          type: parse_json
          time_key: timestamp
          time_format: "%Y-%m-%dT%H:%M:%S.%fZ"
      service:
        pipelines:
          cowrie_pipeline:
            receivers:
              - cowrie_log
            processors:
              - parse_json
    EOF

    systemctl restart google-cloud-ops-agent
  EOT
}

# 7. Firewall Rules
# Allow standard SSH (port 22) for honeypot attackers
resource "google_compute_firewall" "allow_ssh_honeypot" {
  name    = "allow-ssh-honeypot"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["honeypot"]
}

# Allow custom SSH (port 22022) for admin management
resource "google_compute_firewall" "allow_ssh_admin" {
  name    = "allow-ssh-admin"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22022"]
  }

  source_ranges = ["0.0.0.0/0"] # In production, restrict this to user's home IP
  target_tags   = ["ssh-admin"]
}

# 8. Storage bucket for Cloud Function Source Code
resource "google_storage_bucket" "function_bucket" {
  name                        = "${var.project_id}-triage-function-src"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
}

# Note: Cloud Function deploy resources are intentionally omitted to let users
# deploy the code using gcloud CLI during local setups, keeping Terraform simpler.
