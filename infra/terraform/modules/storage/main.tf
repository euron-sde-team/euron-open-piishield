# One private, versioned bucket for everything too large or too transient to keep in
# Postgres.
#
# <name_prefix>-exports (EXPORTS_BUCKET):
#   documents/<org id>/   protected re-exports of a scanned PDF, DOCX or XLSX/CSV upload,
#                         and scan reports; rows keep only the key, downloads go through
#                         the api, which checks the caller's organisation first
#   backups/              database dumps; kept backup_retention_days
#   An overwritten or deleted object stays recoverable for noncurrent_retention_days.
#
# PIIShield's append-only audit_log and its vault_entries table both live in Postgres,
# never in this bucket; an original sensitive value is never written to S3 in any form.
resource "aws_s3_bucket" "exports" {
  #checkov:skip=CKV_AWS_144:Cross-region replication doubles where customer document exports live (a data-residency decision for the operator); versioning and backups cover recovery (docs/guides/operations.md).
  #checkov:skip=CKV_AWS_18:Access logging targets a separate log bucket an operator chooses; CloudTrail data events cover object access (docs/guides/operations.md).
  #checkov:skip=CKV2_AWS_62:No consumer for S3 event notifications; this bucket is provisioned for a future export-storage feature, not yet written to by the app.
  bucket        = "${var.name_prefix}-exports"
  force_destroy = var.force_destroy
}

resource "aws_s3_bucket_versioning" "exports" {
  bucket = aws_s3_bucket.exports.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "exports" {
  bucket                  = aws_s3_bucket.exports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "exports" {
  bucket = aws_s3_bucket.exports.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "exports" {
  bucket = aws_s3_bucket.exports.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.kms_key_arn != null ? "aws:kms" : "AES256"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = var.kms_key_arn != null
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "exports" {
  bucket     = aws_s3_bucket.exports.id
  depends_on = [aws_s3_bucket_versioning.exports]

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  # Replaced or deleted versions stay recoverable for a while, then go.
  rule {
    id     = "expire-noncurrent"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_retention_days
    }
  }

  rule {
    id     = "expire-document-exports"
    status = "Enabled"
    filter {
      prefix = "documents/"
    }
    expiration {
      days = var.export_expiration_days
    }
  }

  rule {
    id     = "expire-backups"
    status = "Enabled"
    filter {
      prefix = "backups/"
    }
    expiration {
      days = var.backup_retention_days
    }
  }
}

# Only needed when a browser fetches exports with JavaScript; a presigned download link
# opened as a navigation needs none, so the default is no CORS at all.
resource "aws_s3_bucket_cors_configuration" "exports" {
  count  = length(var.cors_origins) > 0 ? 1 : 0
  bucket = aws_s3_bucket.exports.id
  cors_rule {
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = var.cors_origins
    allowed_headers = ["*"]
    expose_headers  = ["Content-Disposition", "Content-Length", "ETag"]
    max_age_seconds = 3600
  }
}

data "aws_iam_policy_document" "tls" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.exports.arn, "${aws_s3_bucket.exports.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "exports" {
  count      = var.enforce_tls ? 1 : 0
  bucket     = aws_s3_bucket.exports.id
  policy     = data.aws_iam_policy_document.tls.json
  depends_on = [aws_s3_bucket_public_access_block.exports]
}
