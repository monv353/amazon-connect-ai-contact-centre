#!/usr/bin/env bash
# Deploy the Arunika AI contact centre demo into your own AWS account.
#
# Configuration comes from environment variables (see .env.example):
#   AWS_PROFILE          optional, the AWS CLI profile to use
#   AWS_REGION           default ap-southeast-1 (Singapore)
#   STACK_NAME           default arunika-cc-demo
#   INSTANCE_ALIAS       default arunika-demo-<last 6 digits of account id>; must be globally unique
#   BEDROCK_MODEL_ID     default apac.amazon.nova-lite-v1:0
#   AGENT_HOURS          AlwaysOpen (default) or BusinessHours
#   DEMO_AGENT_PASSWORD  optional; if set, creates the "demo.agent" Connect user with this password
#                        (8-64 chars, upper + lower case + a number). Never commit it.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export AWS_REGION="${AWS_REGION:-ap-southeast-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
STACK_NAME="${STACK_NAME:-arunika-cc-demo}"
BEDROCK_MODEL_ID="${BEDROCK_MODEL_ID:-apac.amazon.nova-lite-v1:0}"
AGENT_HOURS="${AGENT_HOURS:-AlwaysOpen}"

log() { printf '\n==> %s\n' "$*"; }

command -v aws >/dev/null || { echo "aws CLI v2 is required"; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }

log "Checking AWS identity (profile: ${AWS_PROFILE:-default}, region: $AWS_REGION)"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
echo "Account: $ACCOUNT_ID"
INSTANCE_ALIAS="${INSTANCE_ALIAS:-arunika-demo-${ACCOUNT_ID:6:6}}"
ARTIFACT_BUCKET="${ARTIFACT_BUCKET:-${STACK_NAME}-artifacts-${ACCOUNT_ID}-${AWS_REGION}}"

log "Checking the Bedrock inference profile $BEDROCK_MODEL_ID is available in $AWS_REGION"
if ! aws bedrock get-inference-profile --inference-profile-identifier "$BEDROCK_MODEL_ID" \
      --query 'inferenceProfileId' --output text >/dev/null 2>&1; then
  echo "WARNING: could not read inference profile $BEDROCK_MODEL_ID in $AWS_REGION."
  echo "         The bot still deploys, but FAQ answers will fall back to 'connect to an agent'."
  echo "         List options with: aws bedrock list-inference-profiles --type-equals SYSTEM_DEFINED"
fi

log "Ensuring artifact bucket s3://$ARTIFACT_BUCKET exists"
if ! aws s3api head-bucket --bucket "$ARTIFACT_BUCKET" 2>/dev/null; then
  if [ "$AWS_REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$ARTIFACT_BUCKET" >/dev/null
  else
    aws s3api create-bucket --bucket "$ARTIFACT_BUCKET" \
      --create-bucket-configuration LocationConstraint="$AWS_REGION" >/dev/null
  fi
  aws s3api put-public-access-block --bucket "$ARTIFACT_BUCKET" --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
fi

log "Packaging the fulfillment Lambda"
mkdir -p build
LAMBDA_ZIP="$(python3 - <<'PY'
import hashlib, pathlib, zipfile
src = pathlib.Path("lambda/fulfillment")
files = sorted(p for p in src.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
digest = hashlib.sha256()
for p in files:
    digest.update(str(p.relative_to(src)).encode()); digest.update(p.read_bytes())
out = pathlib.Path("build") / f"fulfillment-{digest.hexdigest()[:12]}.zip"
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in files:
        info = zipfile.ZipInfo(str(p.relative_to(src)), date_time=(2020, 1, 1, 0, 0, 0))
        info.external_attr = 0o644 << 16
        z.writestr(info, p.read_bytes(), zipfile.ZIP_DEFLATED)
print(out)
PY
)"
LAMBDA_KEY="lambda/$(basename "$LAMBDA_ZIP")"
aws s3 cp "$LAMBDA_ZIP" "s3://$ARTIFACT_BUCKET/$LAMBDA_KEY" --only-show-errors
echo "Uploaded s3://$ARTIFACT_BUCKET/$LAMBDA_KEY"

log "Rendering the template (inlining connect/flows/inbound-flow.json)"
python3 scripts/render_template.py build/template.yaml

log "Deploying stack $STACK_NAME (the Connect instance takes a few minutes)"
aws cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --template-file build/template.yaml \
  --s3-bucket "$ARTIFACT_BUCKET" --s3-prefix templates \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --tags project=amazon-connect-ai-contact-centre \
  --parameter-overrides \
    InstanceAlias="$INSTANCE_ALIAS" \
    AgentHours="$AGENT_HOURS" \
    BedrockModelId="$BEDROCK_MODEL_ID" \
    LambdaCodeS3Bucket="$ARTIFACT_BUCKET" \
    LambdaCodeS3Key="$LAMBDA_KEY"

output() {
  aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
INSTANCE_ID="$(output ConnectInstanceId)"
ROUTING_PROFILE_ARN="$(output RoutingProfileArn)"
ACCESS_URL="$(output ConnectAccessUrl)"

if [ -n "${DEMO_AGENT_PASSWORD:-}" ]; then
  log "Creating the demo agent user (demo.agent) if it does not exist"
  EXISTING="$(aws connect list-users --instance-id "$INSTANCE_ID" \
    --query "UserSummaryList[?Username=='demo.agent'].Id" --output text)"
  if [ -z "$EXISTING" ]; then
    AGENT_PROFILE_ID="$(aws connect list-security-profiles --instance-id "$INSTANCE_ID" \
      --query "SecurityProfileSummaryList[?Name=='Agent'].Id" --output text)"
    aws connect create-user --instance-id "$INSTANCE_ID" \
      --username demo.agent \
      --password "$DEMO_AGENT_PASSWORD" \
      --identity-info FirstName=Dewi,LastName=Agent \
      --phone-config PhoneType=SOFT_PHONE,AutoAccept=false \
      --security-profile-ids "$AGENT_PROFILE_ID" \
      --routing-profile-id "${ROUTING_PROFILE_ARN##*/}" >/dev/null
    echo "Created demo.agent"
  else
    echo "demo.agent already exists"
  fi
else
  echo
  echo "DEMO_AGENT_PASSWORD not set, so no agent user was created (you can re-run with it later)."
fi

log "Done. Stack outputs:"
aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" --output table

cat <<EOF

Next steps (no phone number needed):
  1. AWS console > Amazon Connect > instance "$INSTANCE_ALIAS" > "Log in for emergency access"
     (this signs you in as an admin with your IAM identity).
  2. In a separate browser profile, open $ACCESS_URL/ccp-v2 and sign in as demo.agent; set status to Available.
  3. Back in the admin site: Dashboard > "Test chat" > Test settings > choose flow
     "Arunika Inbound - AI Assistant" > Apply, then start chatting. See docs/DEMO_SCRIPT.md.
EOF
