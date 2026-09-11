output "ecr_repository_url" {
  description = "URL del repositorio ECR para push de la imagen."
  value       = aws_ecr_repository.scraper.repository_url
}

output "lambda_function_name" {
  description = "Nombre de la función Lambda del scraper."
  value       = aws_lambda_function.scraper.function_name
}

output "lambda_function_arn" {
  value = aws_lambda_function.scraper.arn
}

output "schedule" {
  description = "Cron y zona horaria de la consulta programada."
  value       = "${aws_scheduler_schedule.poll.schedule_expression} (${aws_scheduler_schedule.poll.schedule_expression_timezone})"
}

output "ssm_token_param" {
  description = "Parámetro SSM donde debe cargarse el token de Telegram."
  value       = aws_ssm_parameter.telegram_token.name
}

output "ssm_chat_id_param" {
  value = aws_ssm_parameter.telegram_chat_id.name
}
