# Control de costos de la cuenta ai-platform-arheanja (080891698277).
# Premisa del proyecto: mantenerse en $0 / free tier. Este budget alerta ante
# cualquier gasto real. AWS Budgets: 2 gratis por cuenta.
#
# Creado primero por CLI durante la migración; se adopta al state con import
# para gestionarlo como código.

import {
  to = aws_budgets_budget.zero_spend
  id = "${local.account_id}:ai-platform-zero-spend"
}

resource "aws_budgets_budget" "zero_spend" {
  name         = "ai-platform-zero-spend"
  budget_type  = "COST"
  limit_amount = "1"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Cualquier gasto real dispara alerta (premisa $0).
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 0.01
    threshold_type             = "ABSOLUTE_VALUE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["taxopsa@gmail.com"]
  }

  # Forecast por encima del límite.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = ["taxopsa@gmail.com"]
  }
}
