# --- API Gateway HTTP para el webhook de Telegram (comandos a demanda) ---

resource "aws_apigatewayv2_api" "webhook" {
  name          = "${var.project}-webhook"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "webhook" {
  api_id                 = aws_apigatewayv2_api.webhook.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.scraper.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "webhook" {
  api_id    = aws_apigatewayv2_api.webhook.id
  route_key = "POST /telegram"
  target    = "integrations/${aws_apigatewayv2_integration.webhook.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.webhook.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scraper.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.webhook.execution_arn}/*/*"
}

# Permite que la Lambda se auto-invoque (async) para el scrape de /consultar.
resource "aws_iam_role_policy" "self_invoke" {
  name = "${var.project}-self-invoke"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.scraper.arn
    }]
  })
}

# Secret del webhook (anti-spoofing). Valor real se carga con `aws ssm put-parameter`.
resource "aws_ssm_parameter" "webhook_secret" {
  name  = "/${var.project}/telegram_webhook_secret"
  type  = "SecureString"
  value = "PLACEHOLDER"

  lifecycle {
    ignore_changes = [value]
  }
}

output "webhook_url" {
  description = "URL del webhook para registrar en Telegram (setWebhook)."
  value       = "${aws_apigatewayv2_api.webhook.api_endpoint}/telegram"
}
