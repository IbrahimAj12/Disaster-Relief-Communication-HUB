# 1. LE PARE-FEU (CRITIQUE : Ouvre la porte 3000)
resource "google_compute_firewall" "allow-rocketchat" {
  name    = "allow-rocketchat-access"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["3000", "22"]
  }
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["rocketchat"] # Ce tag doit correspondre à celui de la VM ci-dessous
}

# 2. LA MACHINE VIRTUELLE
resource "google_compute_instance" "disaster_vm" {
  name         = var.vm_name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["rocketchat", "http-server"] # Le tag qui active le pare-feu

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 30
    }
  }

  network_interface {
    network = "default"
    access_config {} # IP Publique
  }

  metadata = {
    ssh-keys = "${var.ssh_user}:${file(pathexpand(var.ssh_public_key))}"
  }

  # 3. LE SCRIPT DE DÉMARRAGE (Installe tout tout seul)
  metadata_startup_script = <<-EOF
    #!/bin/bash
    # Installation de Docker
    apt-get update && apt-get install -y docker.io docker-compose-v2
    
    # Création du dossier
    mkdir -p /home/${var.ssh_user}/hub
    cd /home/${var.ssh_user}/hub

    # Création du fichier docker-compose.yml (Version MongoDB 5.0 Solide)
    cat <<EOT > docker-compose.yml
    version: '3.8'
    services:
      mongo:
        image: mongo:5.0
        restart: always
        volumes:
          - ./data/db:/data/db
        command: mongod --oplogSize 128 --replSet rs0 --bind_ip_all
      
      mongo-init-replica:
        image: mongo:5.0
        command: >
          bash -c "for i in \`seq 1 30\`; do
            mongosh mongodb://mongo:27017/ --eval 'rs.initiate({ _id: \"rs0\", members: [ { _id: 0, host: \"mongo:27017\" } ] })' &&
            s=\$\$? && break || s=\$\$?;
            sleep 5;
          done; (exit \$\$s)"
        depends_on:
          - mongo
      
      rocketchat:
        image: rocket.chat:6.12.0
        restart: always
        environment:
          - PORT=3000
          - ROOT_URL=http://localhost:3000
          - MONGO_URL=mongodb://mongo:27017/rocketchat
          - MONGO_OPLOG_URL=mongodb://mongo:27017/local?replicaSet=rs0
        ports:
          - "3000:3000"
        depends_on:
          - mongo
          - mongo-init-replica
    EOT

    # Lancement
    docker compose up -d
  EOF
}
