#!/usr/bin/env bash
# Delete everything deploy.sh created: the stack (Connect instance, Lex bot, Lambda, S3 storage)
# and the artifact bucket. Uses the same environment variables as deploy.sh.
#   FORCE=1          skip the confirmation prompt
#   KEEP_ARTIFACTS=1 keep the artifact bucket
set -euo pipefail

export AWS_REGION="${AWS_REGION:-ap-southeast-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
STACK_NAME="${STACK_NAME:-arunika-cc-demo}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ARTIFACT_BUCKET="${ARTIFACT_BUCKET:-${STACK_NAME}-artifacts-${ACCOUNT_ID}-${AWS_REGION}}"

cat <<EOF
This permanently deletes, in account $ACCOUNT_ID / $AWS_REGION:
  - stack $STACK_NAME, including the Amazon Connect instance, its users, flows,
    chat transcripts, recordings and Contact Lens output
  - artifact bucket s3://$ARTIFACT_BUCKET (unless KEEP_ARTIFACTS=1)
Note: AWS limits how many Connect instances you can create/delete in 30 days.
Any phone number you claimed is released when the instance is deleted.
EOF

if [ "${FORCE:-0}" != "1" ]; then
  read -r -p "Type the stack name to confirm: " answer
  [ "$answer" = "$STACK_NAME" ] || { echo "Aborted."; exit 1; }
fi

if aws cloudformation describe-stacks --stack-name "$STACK_NAME" >/dev/null 2>&1; then
  STORAGE_BUCKET="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='StorageBucketName'].OutputValue" --output text)"
  if [ -n "$STORAGE_BUCKET" ] && [ "$STORAGE_BUCKET" != "None" ]; then
    echo "Emptying s3://$STORAGE_BUCKET"
    aws s3 rm "s3://$STORAGE_BUCKET" --recursive --only-show-errors || true
  fi
  echo "Deleting stack $STACK_NAME"
  aws cloudformation delete-stack --stack-name "$STACK_NAME"
  aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME"
  echo "Stack deleted."
else
  echo "Stack $STACK_NAME not found, skipping."
fi

if [ "${KEEP_ARTIFACTS:-0}" != "1" ] && aws s3api head-bucket --bucket "$ARTIFACT_BUCKET" 2>/dev/null; then
  echo "Deleting artifact bucket s3://$ARTIFACT_BUCKET"
  aws s3 rb "s3://$ARTIFACT_BUCKET" --force >/dev/null
fi

echo "Teardown complete. Check Billing > Bills tomorrow to confirm no further charges."
