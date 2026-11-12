variable "endpoint" {
  description = "Emulator endpoint. http://floci:4566 inside compose, http://localhost:5566 from the host."
  type        = string
  default     = "http://localhost:5566"
}

variable "name_prefix" {
  description = "Must match EXPORTS_BUCKET (<name_prefix>-exports) and KMS_KEY_ID (alias/<name_prefix>) in deploy/compose/compose.floci.yaml."
  type        = string
  default     = "piishield-local"
}

variable "cors_origins" {
  description = "Dashboard origins allowed to fetch objects with JavaScript."
  type        = list(string)
  default     = ["http://localhost:5510", "http://127.0.0.1:5510"]
}

variable "mail_domain" {
  description = "SES domain identity created on the emulator (the domain of MAIL_FROM_ADDRESS locally)."
  type        = string
  default     = "piishield.local"
}

variable "mail_from_address" {
  description = "From address the send policy allows (MAIL_FROM_ADDRESS locally)."
  type        = string
  default     = "alerts@piishield.local"
}
