variable "aws_region" {
  description = "Región AWS."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Prefijo/identificador del proyecto."
  type        = string
  default     = "dianbot"
}

variable "image_tag" {
  description = "Tag de la imagen en ECR a desplegar en la Lambda."
  type        = string
  default     = "latest"
}

variable "lambda_memory_mb" {
  description = "Memoria de la Lambda (Chromium necesita bastante)."
  type        = number
  default     = 3008
}

variable "lambda_timeout_s" {
  description = "Timeout de la Lambda en segundos."
  type        = number
  default     = 120
}

variable "poll_interval_min" {
  description = "Cada cuántos minutos consultar dentro de la ventana horaria."
  type        = number
  default     = 10
}

# Ventana de consulta: Lunes a Viernes, 07:00–17:00 America/Bogota.
# EventBridge Scheduler soporta timezone, así que el cron va en hora local.
variable "schedule_expression" {
  description = "Cron de EventBridge Scheduler (hora local America/Bogota)."
  type        = string
  # Cada 10 min, de 07:00 a 16:59, Lunes a Viernes.
  default = "cron(0/10 7-16 ? * MON-FRI *)"
}

variable "notify_mode" {
  description = "only_hits (solo avisa si hay citas) | always (avisa siempre)."
  type        = string
  default     = "only_hits"
}

variable "dian_categoria" {
  type    = string
  default = "Devoluciones"
}

variable "dian_tipo_atencion" {
  type    = string
  default = "Videoatención"
}
