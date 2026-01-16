variable "project_id" {
  default = "disaster-relief-hub-484419"  # <--- C'était 484416, j'ai mis 484419 (vérifie ton gcloud list !)
}

variable "region" {
  default = "europe-west1"
}

variable "zone" {
  default = "europe-west1-b"
}

variable "vm_name" {
  default = "disaster-relief-vm"
}

variable "machine_type" {
  default = "e2-medium"
}

variable "ssh_user" {
  default = "ubuntu" # Utilise "ubuntu" c'est plus standard sur GCP
}

variable "ssh_public_key" {
  description = "SSH public key path"
  default     = "./gcp_key.pub" # <--- Ajouté pour te simplifier la vie
}
