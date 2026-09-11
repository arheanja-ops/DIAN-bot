# --- Función Lambda (imagen de contenedor) ---
resource "aws_lambda_function" "scraper" {
  function_name = "${var.project}-scraper"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = local.image_uri
  architectures = ["arm64"]
  memory_size   = var.lambda_memory_mb
  timeout       = var.lambda_timeout_s

  environment {
    variables = {
      DIAN_TIPO_ATENCION = var.dian_tipo_atencion
      DIAN_CATEGORIA     = var.dian_categoria
      NOTIFY_MODE        = var.notify_mode
      TZ                 = "America/Bogota"
      STATE_PATH         = "/tmp/last.json"
      HISTORY_PATH       = "/tmp/history.jsonl"
      # Nombres de los parámetros SSM con los secretos (el handler los lee).
      SSM_TOKEN_PARAM          = aws_ssm_parameter.telegram_token.name
      SSM_CHAT_ID_PARAM        = aws_ssm_parameter.telegram_chat_id.name
      SSM_WEBHOOK_SECRET_PARAM = aws_ssm_parameter.webhook_secret.name
    }
  }

  # La imagen la publica el pipeline de la app; Terraform no debe forzar
  # rollback al tag anterior en cada plan.
  lifecycle {
    ignore_changes = [image_uri]
  }
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.scraper.function_name}"
  retention_in_days = 14
}

# --- EventBridge Scheduler: L-V 07:00–17:00 Bogotá cada N minutos ---
resource "aws_scheduler_schedule" "poll" {
  name = "${var.project}-poll"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = "America/Bogota"

  target {
    arn      = aws_lambda_function.scraper.arn
    role_arn = aws_iam_role.scheduler.arn
  }
}

# Rol que permite a EventBridge Scheduler invocar la Lambda.
resource "aws_iam_role" "scheduler" {
  name = "${var.project}-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "scheduler_invoke" {
  name = "${var.project}-scheduler-invoke"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.scraper.arn
    }]
  })
}
