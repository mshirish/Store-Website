# ── General ───────────────────────────────────────────────────────────────────

variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-2"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

# ── Access ────────────────────────────────────────────────────────────────────

variable "my_ip_cidr" {
  description = "Your public IP as /32, allowed to SSH to instances. Empty = no SSH rule."
  type        = string
  default     = ""
}

variable "key_name" {
  description = "Existing EC2 key pair name for SSH. Empty = no key pair."
  type        = string
  default     = ""
}

# ── Sizing ────────────────────────────────────────────────────────────────────

variable "instance_type" {
  description = "EC2 instance type for the app servers."
  type        = string
  default     = "t3.small"
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t3.micro"
}

# ── Database ──────────────────────────────────────────────────────────────────

variable "db_name" {
  description = "Postgres database name (letters, digits, underscores; must start with a letter)."
  type        = string
  default     = "store_db"
}

variable "db_username" {
  description = "Postgres master username."
  type        = string
  default     = "store_user"
}

variable "db_password" {
  description = "Postgres master password (8+ chars; RDS forbids / @ \" and spaces)."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.db_password) >= 8 && !can(regex("[/@\" ]", var.db_password))
    error_message = "db_password must be at least 8 characters and must not contain /, @, \" or spaces."
  }
}

# ── Django / Stripe ───────────────────────────────────────────────────────────

variable "django_secret_key" {
  description = "Django SECRET_KEY (long random string)."
  type        = string
  sensitive   = true
}

variable "stripe_publishable_key" {
  description = "Stripe TEST publishable key (pk_test_...)."
  type        = string
  sensitive   = true
}

variable "stripe_secret_key" {
  description = "Stripe TEST secret key (sk_test_...)."
  type        = string
  sensitive   = true
}

# ── Media storage (Cloudflare R2) — leave all blank to keep media on the instance ──

variable "r2_access_key_id" {
  description = "R2 API token access key ID."
  type        = string
  sensitive   = true
  default     = ""
}

variable "r2_secret_access_key" {
  description = "R2 API token secret access key."
  type        = string
  sensitive   = true
  default     = ""
}

variable "r2_bucket_name" {
  description = "R2 bucket name."
  type        = string
  default     = ""
}

variable "r2_endpoint_url" {
  description = "R2 S3 API endpoint, e.g. https://<account-id>.r2.cloudflarestorage.com"
  type        = string
  default     = ""
}

variable "r2_public_url" {
  description = "Bucket public URL, e.g. https://pub-xxxx.r2.dev"
  type        = string
  default     = ""
}

# ── App ───────────────────────────────────────────────────────────────────────

variable "repo_url" {
  description = "Public Git repository to clone onto each instance."
  type        = string
  default     = "https://github.com/mshirish/Store-Website.git"
}

variable "app_port" {
  description = "Host port the app container is published on (ALB target port)."
  type        = number
  default     = 8000
}
