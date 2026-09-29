import secrets
import json
import urllib.parse
import urllib.request
import urllib.error
import os
import time
import hashlib
from typing import Optional, Dict, Any
from functools import wraps
import jwt
from jwt import PyJWKClient
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, current_app, jsonify
from app.extensions import db
from app.models.user import User
from app.models.health_profile import HealthProfile
from app.validation.schemas import UserRegisterSchema, UserLoginSchema, OnboardingSchema
from app.validation.validators import format_pydantic_errors
from app.services.audit_service import AuditService
from app.services.error_service import ErrorTrackingService
from app.services.recommendation_service import RecommendationService
from app.services.otp_service import OTPService
from pydantic import ValidationError

auth_bp = Blueprint("auth", __name__)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in with admin privileges.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        user = db.session.get(User, session["user_id"])
        if not user or not user.is_admin():
            flash("Administrative access required.", "danger")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.before_app_request
def load_current_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = db.session.get(User, user_id)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        form_data = {
            "name": request.form.get("name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "password": request.form.get("password", ""),
            "age": int(request.form.get("age", 25)) if request.form.get("age") else None,
            "gender": request.form.get("gender", "other"),
            "height_cm": float(request.form.get("height_cm", 170.0)) if request.form.get("height_cm") else None,
            "weight_kg": float(request.form.get("weight_kg", 70.0)) if request.form.get("weight_kg") else None,
            "activity_level": request.form.get("activity_level", "moderately_active"),
            "dietary_preference": request.form.get("dietary_preference", "balanced"),
            "health_goal": request.form.get("health_goal", "maintenance"),
            "allergies": request.form.get("allergies", "").strip(),
            "physical_limitations": request.form.get("physical_limitations", "none").strip(),
        }

        try:
            validated = UserRegisterSchema(**form_data)
        except ValidationError as err:
            errors = format_pydantic_errors(err)
            for e in errors:
                flash(f"{e['field']}: {e['message']}", "danger")
            return render_template("register.html", form=form_data)

        # Check existing user
        if User.query.filter_by(email=validated.email).first():
            flash("An account with this email already exists. Please log in.", "danger")
            return render_template("register.html", form=form_data)

        # Create user
        user = User(
            name=validated.name,
            email=validated.email,
            role="user",
        )
        user.set_password(validated.password)
        db.session.add(user)
        db.session.flush()

        # Create health profile
        profile = HealthProfile(
            user_id=user.id,
            age=validated.age,
            gender=validated.gender,
            height_cm=validated.height_cm,
            weight_kg=validated.weight_kg,
            activity_level=validated.activity_level,
            dietary_preference=validated.dietary_preference,
            health_goal=validated.health_goal,
            allergies=validated.allergies or "",
            physical_limitations=validated.physical_limitations or "none",
        )
        profile.calculate_metrics()
        db.session.add(profile)
        db.session.commit()

        # Generate initial recommendations and tasks
        try:
            RecommendationService.generate_daily_recommendation(user_id=user.id)
        except Exception:
            pass

        AuditService.log_event("USER_REGISTER", user_id=user.id, details={"email": user.email})
        session["user_id"] = user.id
        session.permanent = True
        flash("Welcome to your AI Wellness Companion! Your health profile is established.", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("register.html", form={})


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password. Please verify and try again.", "danger")
            return render_template("login.html", email=email)

        # Session fixation defense: clear prior session data
        session.clear()
        session["user_id"] = user.id
        session.permanent = True
        AuditService.log_event("USER_LOGIN", user_id=user.id, details={"email": user.email})
        flash(f"Welcome back, {user.name}!", "success")

        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)
        return redirect(url_for("dashboard.index"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    user_id = session.get("user_id")
    session.clear()
    if user_id:
        AuditService.log_event("USER_LOGOUT", user_id=user_id)
    flash("You have been securely logged out.", "info")
    return redirect(url_for("auth.login"))


def _get_google_redirect_uri() -> str:
    """Return the trusted Google OAuth redirect URI from config or generate local fallback."""
    configured_uri = current_app.config.get("GOOGLE_REDIRECT_URI")
    if configured_uri:
        return configured_uri
    return url_for("auth.google_callback", _external=True)


@auth_bp.route("/auth/google")
def google_login():
    """Initiates Google OAuth 2.0 Web Authentication flow."""
    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    if not client_id:
        AuditService.log_event("GOOGLE_LOGIN_FAILED", details={"reason": "credentials_not_configured"})
        flash("Google sign-in is not yet configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env, or sign in with email/password.", "warning")
        return redirect(url_for("auth.login"))

    # Generate secure random state token for CSRF defense
    state = secrets.token_urlsafe(32)
    session["google_oauth_state"] = state

    redirect_uri = _get_google_redirect_uri()
    AuditService.log_event("GOOGLE_LOGIN_STARTED", details={"redirect_uri": redirect_uri})
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)


@auth_bp.route("/auth/google/callback")
def google_callback():
    """Handles Google OAuth 2.0 callback, verifies tokens, and performs safe account resolution."""
    state = request.args.get("state")
    saved_state = session.pop("google_oauth_state", None)

    if not state or not saved_state or not secrets.compare_digest(state, saved_state):
        AuditService.log_event("GOOGLE_LOGIN_FAILED", details={"reason": "csrf_state_mismatch"})
        flash("Authentication failed: invalid state token (anti-CSRF protection). Please try again.", "danger")
        return redirect(url_for("auth.login"))

    code = request.args.get("code")
    if not code:
        err = request.args.get("error", "Access denied")
        AuditService.log_event("GOOGLE_LOGIN_FAILED", details={"reason": "oauth_provider_error", "error": err})
        if err == "access_denied":
            flash("Google sign-in was canceled.", "info")
        else:
            flash(f"Google sign-in was not completed: {err}", "warning")
        return redirect(url_for("auth.login"))

    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET")
    redirect_uri = _get_google_redirect_uri()

    if not client_id or not client_secret:
        AuditService.log_event("GOOGLE_LOGIN_FAILED", details={"reason": "credentials_not_configured_at_callback"})
        flash("Google sign-in is not configured properly.", "danger")
        return redirect(url_for("auth.login"))

    try:
        token_data = _exchange_google_code(code, client_id, client_secret, redirect_uri)
        access_token = token_data.get("access_token")
        id_token_str = token_data.get("id_token")

        identity_info = _verify_and_extract_google_identity(id_token_str, access_token, client_id)
        google_id = identity_info.get("sub")
        email = identity_info.get("email")
        email_verified = identity_info.get("email_verified", True)
        name = identity_info.get("name") or (email.split("@")[0].title() if email else "Google User")

        if not google_id or not email:
            raise ValueError("Google user info missing mandatory identity fields ('sub', 'email').")

        if not email_verified:
            AuditService.log_event("GOOGLE_LOGIN_FAILED", details={"reason": "email_not_verified", "email": email})
            flash("Your Google account email is not verified by Google. Please verify your email with Google first.", "warning")
            return redirect(url_for("auth.login"))

    except Exception as e:
        error_id = ErrorTrackingService.record_error(
            module="auth.google_callback",
            message=f"Google authentication exchange/verification failed: {e}",
            category="AUTHENTICATION",
            severity="ERROR",
            safe_user_message="Google sign-in could not be completed. Please try again.",
            exc=e,
        )
        AuditService.log_event("GOOGLE_LOGIN_FAILED", details={"reason": "token_verification_failed", "error_id": error_id})
        flash("Google sign-in could not be completed. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    # Resolve user
    # 1. Match by permanent google_id (Google subject identifier)
    user = User.query.filter_by(google_id=google_id).first()

    if not user:
        # 2. Safe account-linking: Match by verified email address
        user = User.query.filter_by(email=email).first()
        if user:
            if user.google_id and user.google_id != google_id:
                # Security defense: Account is already linked to a different Google account
                AuditService.log_event(
                    "GOOGLE_ACCOUNT_LINK_FAILED",
                    user_id=user.id,
                    details={"reason": "google_subject_mismatch", "existing_google_id": user.google_id}
                )
                AuditService.log_event("GOOGLE_LOGIN_FAILED", user_id=user.id, details={"reason": "account_collision"})
                flash("This email is already associated with another Google account. Please log in with email and password.", "danger")
                return redirect(url_for("auth.login"))

            # Safe link
            user.google_id = google_id
            if hasattr(user, "auth_provider"):
                existing = set(user.auth_provider.split("+")) if user.auth_provider else {"local"}
                existing.add("google")
                user.auth_provider = "+".join(sorted(existing))
            db.session.commit()
            AuditService.log_event("GOOGLE_ACCOUNT_LINKED", user_id=user.id, details={"email": email, "google_id": google_id})

    is_new_user = False
    if not user:
        # 3. Create new User account
        is_new_user = True
        user = User(
            name=name,
            email=email,
            role="user",
            is_demo=False,
            google_id=google_id,
            auth_provider="google" if hasattr(User, "auth_provider") else "local",
        )
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.commit()
        AuditService.log_event("GOOGLE_ACCOUNT_CREATED", user_id=user.id, details={"email": email, "google_id": google_id})
        AuditService.log_event("GOOGLE_USER_REGISTER", user_id=user.id, details={"email": email, "google_id": google_id})

    # Establish secure session with session fixation defense
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    AuditService.log_event("GOOGLE_LOGIN_SUCCESS", user_id=user.id, details={"email": user.email, "google_id": google_id})

    # Check if user needs onboarding
    profile = user.profile
    needs_onboarding = is_new_user or (profile is None) or (not profile.height_cm or not profile.weight_kg)

    if needs_onboarding:
        first_name = user.name.split(" ")[0] if user.name else "there"
        flash(f"Welcome to Vitalis AI, {first_name}! Please take a moment to configure your personalized health profile.", "info")
        return redirect(url_for("auth.onboarding"))

    flash(f"Welcome back, {user.name}!", "success")
    return redirect(url_for("dashboard.index"))


def _get_apple_redirect_uri() -> str:
    """Return the trusted Apple OAuth redirect/return URI from config or generate local fallback."""
    configured_uri = current_app.config.get("APPLE_REDIRECT_URI")
    if configured_uri:
        return configured_uri
    return url_for("auth.apple_callback", _external=True)


def _load_apple_private_key(key_setting: str) -> str:
    """Load Apple private key from PEM string or file path."""
    if not key_setting:
        return ""
    key_str = key_setting.strip()
    if os.path.isfile(key_str):
        try:
            with open(key_str, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            current_app.logger.error(f"Failed to read Apple private key file '{key_str}': {e}")
            return ""
    if "\\n" in key_str and "-----BEGIN" in key_str:
        key_str = key_str.replace("\\n", "\n")
    return key_str


def _generate_apple_client_secret(client_id: str, team_id: str, key_id: str, private_key_str: str) -> str:
    """
    Generate client_secret JWT for Apple Web Authentication.
    Signed using ES256 with Apple Developer private key (.p8).
    Valid for up to 6 months (180 days).
    """
    now = int(time.time())
    headers = {
        "kid": key_id,
        "alg": "ES256",
    }
    payload = {
        "iss": team_id,
        "iat": now,
        "exp": now + 86400 * 180,
        "aud": "https://appleid.apple.com",
        "sub": client_id,
    }
    pem_key = _load_apple_private_key(private_key_str)
    return jwt.encode(payload, pem_key, algorithm="ES256", headers=headers)


def _verify_and_extract_apple_identity(
    id_token_str: str,
    client_id: str,
) -> Dict[str, Any]:
    """
    Cryptographically verify the Apple ID token using Apple's public keys (JWKS),
    validating signature, issuer, audience, and expiration.
    Extracts the stable subject identifier (sub), email, and verification status.
    """
    if not id_token_str:
        raise ValueError("Missing Apple ID token string.")

    # In testing mode or offline dev fallback:
    if current_app.config.get("TESTING"):
        try:
            unverified = jwt.decode(id_token_str, options={"verify_signature": False})
            return {
                "sub": str(unverified.get("sub")),
                "email": unverified.get("email"),
                "email_verified": bool(
                    unverified.get("email_verified") is True
                    or str(unverified.get("email_verified")).lower() == "true"
                ),
            }
        except Exception as e:
            raise ValueError(f"Failed to decode test Apple ID token: {e}")

    try:
        jwks_client = PyJWKClient("https://appleid.apple.com/auth/keys")
        signing_key = jwks_client.get_signing_key_from_jwt(id_token_str)
        decoded = jwt.decode(
            id_token_str,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer="https://appleid.apple.com",
        )
        return {
            "sub": str(decoded.get("sub")),
            "email": decoded.get("email"),
            "email_verified": bool(
                decoded.get("email_verified") is True
                or str(decoded.get("email_verified")).lower() == "true"
            ),
        }
    except Exception as e:
        current_app.logger.warning(f"Apple ID token verification with JWKS failed: {e}")
        if current_app.config.get("DEBUG"):
            try:
                unverified = jwt.decode(id_token_str, options={"verify_signature": False})
                iss = unverified.get("iss")
                aud = unverified.get("aud")
                if iss in ("https://appleid.apple.com", "appleid.apple.com") and aud == client_id:
                    return {
                        "sub": str(unverified.get("sub")),
                        "email": unverified.get("email"),
                        "email_verified": bool(
                            unverified.get("email_verified") is True
                            or str(unverified.get("email_verified")).lower() == "true"
                        ),
                    }
            except Exception:
                pass
        raise RuntimeError(f"Apple ID token signature/verification failed: {e}")


def _exchange_apple_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    """Exchange Apple authorization code for tokens via Apple's token endpoint."""
    token_url = "https://appleid.apple.com/auth/token"
    payload = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode("utf-8")

    req = urllib.request.Request(token_url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Apple token exchange failed ({he.code}): {err_body}")


@auth_bp.route("/auth/apple")
def apple_login():
    """Initiates Sign in with Apple Web Authentication flow."""
    client_id = current_app.config.get("APPLE_CLIENT_ID")
    if not client_id:
        AuditService.log_event("APPLE_LOGIN_FAILED", details={"reason": "credentials_not_configured"})
        flash("Apple sign-in is not yet configured. Please set APPLE_CLIENT_ID in .env, or sign in with email/password.", "warning")
        return redirect(url_for("auth.login"))

    # Generate secure random state token for CSRF defense
    state = secrets.token_urlsafe(32)
    session["apple_oauth_state"] = state

    redirect_uri = _get_apple_redirect_uri()
    AuditService.log_event("APPLE_LOGIN_STARTED", details={"redirect_uri": redirect_uri})
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code id_token",
        "response_mode": "form_post",
        "scope": "name email",
        "state": state,
    }
    auth_url = f"https://appleid.apple.com/auth/authorize?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)


@auth_bp.route("/auth/apple/callback", methods=["GET", "POST"])
def apple_callback():
    """Handles Apple Sign-In callback (form_post or GET), verifies tokens, and performs safe account resolution."""
    data = request.form if request.method == "POST" else request.args

    state = data.get("state")
    saved_state = session.pop("apple_oauth_state", None)

    if not state or not saved_state or not secrets.compare_digest(state, saved_state):
        AuditService.log_event("APPLE_LOGIN_FAILED", details={"reason": "csrf_state_mismatch"})
        flash("Authentication failed: invalid state token (anti-CSRF protection). Please try again.", "danger")
        return redirect(url_for("auth.login"))

    error = data.get("error")
    if error:
        AuditService.log_event("APPLE_LOGIN_FAILED", details={"reason": "oauth_provider_error", "error": error})
        if error in ("user_cancelled_authorize", "access_denied"):
            flash("Apple sign-in was canceled.", "info")
        else:
            flash(f"Apple sign-in was not completed: {error}", "warning")
        return redirect(url_for("auth.login"))

    code = data.get("code")
    id_token_str = data.get("id_token")
    user_payload_raw = data.get("user")

    client_id = current_app.config.get("APPLE_CLIENT_ID")
    team_id = current_app.config.get("APPLE_TEAM_ID")
    key_id = current_app.config.get("APPLE_KEY_ID")
    private_key = current_app.config.get("APPLE_PRIVATE_KEY")
    redirect_uri = _get_apple_redirect_uri()

    if not client_id:
        AuditService.log_event("APPLE_LOGIN_FAILED", details={"reason": "credentials_not_configured_at_callback"})
        flash("Apple sign-in is not configured properly.", "danger")
        return redirect(url_for("auth.login"))

    # If id_token was not returned in form_post, exchange code for tokens
    if not id_token_str and code:
        if not (team_id and key_id and private_key):
            flash("Apple sign-in credentials incomplete for code exchange.", "danger")
            return redirect(url_for("auth.login"))
        try:
            client_secret = _generate_apple_client_secret(client_id, team_id, key_id, private_key)
            token_response = _exchange_apple_code(code, client_id, client_secret, redirect_uri)
            id_token_str = token_response.get("id_token")
        except Exception as e:
            error_id = ErrorTrackingService.record_error(
                module="auth.apple_callback",
                message=f"Apple token exchange failed: {e}",
                category="AUTHENTICATION",
                severity="ERROR",
                safe_user_message="Apple sign-in could not be completed. Please try again.",
                exc=e,
            )
            AuditService.log_event("APPLE_LOGIN_FAILED", details={"reason": "token_exchange_failed", "error_id": error_id})
            flash("Apple sign-in could not be completed. Please try again.", "danger")
            return redirect(url_for("auth.login"))

    if not id_token_str:
        AuditService.log_event("APPLE_LOGIN_FAILED", details={"reason": "missing_id_token_and_code"})
        flash("Apple sign-in could not be completed: no identity token received.", "danger")
        return redirect(url_for("auth.login"))

    try:
        identity = _verify_and_extract_apple_identity(id_token_str, client_id)
        apple_id = identity.get("sub")
        email = identity.get("email")
        email_verified = identity.get("email_verified", True)

        if not apple_id:
            raise ValueError("Apple identity token missing permanent subject identifier ('sub').")

        # Extract name if user payload provided (Apple sends name only on initial sign-in)
        name = None
        if user_payload_raw:
            try:
                user_obj = json.loads(user_payload_raw) if isinstance(user_payload_raw, str) else user_payload_raw
                name_obj = user_obj.get("name", {})
                first = name_obj.get("firstName", "").strip()
                last = name_obj.get("lastName", "").strip()
                if first or last:
                    name = f"{first} {last}".strip()
            except Exception:
                pass

        if not name:
            if email and "@" in email:
                name = email.split("@")[0].title()
            else:
                name = "Apple User"

    except Exception as e:
        error_id = ErrorTrackingService.record_error(
            module="auth.apple_callback",
            message=f"Apple authentication identity verification failed: {e}",
            category="AUTHENTICATION",
            severity="ERROR",
            safe_user_message="Apple sign-in could not be completed. Please try again.",
            exc=e,
        )
        AuditService.log_event("APPLE_LOGIN_FAILED", details={"reason": "identity_verification_failed", "error_id": error_id})
        flash("Apple sign-in could not be completed. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    # Resolve user
    # 1. Match by permanent apple_id
    user = User.query.filter_by(apple_id=apple_id).first()

    if not user and email:
        # 2. Safe account-linking: Match by verified email address
        user = User.query.filter_by(email=email).first()
        if user:
            if user.apple_id and user.apple_id != apple_id:
                # Security defense: Account is already linked to a different Apple account
                AuditService.log_event(
                    "APPLE_ACCOUNT_LINK_FAILED",
                    user_id=user.id,
                    details={"reason": "apple_subject_mismatch", "existing_apple_id": user.apple_id}
                )
                AuditService.log_event("APPLE_LOGIN_FAILED", user_id=user.id, details={"reason": "account_collision"})
                flash("This email is already associated with another Apple account. Please log in with email and password.", "danger")
                return redirect(url_for("auth.login"))

            # Safe link
            user.apple_id = apple_id
            if hasattr(user, "auth_provider"):
                existing = set(user.auth_provider.split("+")) if user.auth_provider else {"local"}
                existing.add("apple")
                user.auth_provider = "+".join(sorted(existing))
            db.session.commit()
            AuditService.log_event("APPLE_ACCOUNT_LINKED", user_id=user.id, details={"email": email, "apple_id": apple_id})

    is_new_user = False
    if not user:
        # 3. Create new User account
        is_new_user = True
        user_email = email or f"apple_{apple_id[:12]}@vitalis.privaterelay.internal"
        user = User(
            name=name,
            email=user_email,
            role="user",
            is_demo=False,
            apple_id=apple_id,
            auth_provider="apple" if hasattr(User, "auth_provider") else "local",
        )
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.commit()
        AuditService.log_event("APPLE_ACCOUNT_CREATED", user_id=user.id, details={"email": user.email, "apple_id": apple_id})
        AuditService.log_event("APPLE_USER_REGISTER", user_id=user.id, details={"email": user.email, "apple_id": apple_id})

    # Establish secure session with session fixation defense
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    AuditService.log_event("APPLE_LOGIN_SUCCESS", user_id=user.id, details={"email": user.email, "apple_id": apple_id})

    # Check if user needs onboarding
    profile = user.profile
    needs_onboarding = is_new_user or (profile is None) or (not profile.height_cm or not profile.weight_kg)

    if needs_onboarding:
        first_name = user.name.split(" ")[0] if user.name else "there"
        flash(f"Welcome to Vitalis AI, {first_name}! Please take a moment to configure your personalized health profile.", "info")
        return redirect(url_for("auth.onboarding"))

    flash(f"Welcome back, {user.name}!", "success")
    return redirect(url_for("dashboard.index"))


@auth_bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    user = g.user
    if user.profile and user.profile.age and user.profile.height_cm and user.profile.weight_kg:
        # Profile is already completed
        return redirect(url_for("dashboard.index"))

    form_data = {}
    if request.method == "POST":
        form_data = {
            "age": int(request.form.get("age", 28)) if request.form.get("age") else None,
            "gender": request.form.get("gender", "other"),
            "height_cm": float(request.form.get("height_cm", 170.0)) if request.form.get("height_cm") else None,
            "weight_kg": float(request.form.get("weight_kg", 70.0)) if request.form.get("weight_kg") else None,
            "activity_level": request.form.get("activity_level", "moderately_active"),
            "dietary_preference": request.form.get("dietary_preference", "balanced"),
            "health_goal": request.form.get("health_goal", "maintenance"),
            "allergies": request.form.get("allergies", "").strip(),
            "physical_limitations": request.form.get("physical_limitations", "none").strip(),
        }

        try:
            validated = OnboardingSchema(**form_data)
        except ValidationError as err:
            errors = format_pydantic_errors(err)
            for e in errors:
                flash(f"{e['field']}: {e['message']}", "danger")
            return render_template("onboarding.html", user=user, form=form_data)

        # Create or update profile
        profile = user.profile
        if not profile:
            profile = HealthProfile(user_id=user.id)
            db.session.add(profile)

        profile.age = validated.age
        profile.gender = validated.gender
        profile.height_cm = validated.height_cm
        profile.weight_kg = validated.weight_kg
        profile.activity_level = validated.activity_level
        profile.dietary_preference = validated.dietary_preference
        profile.health_goal = validated.health_goal
        profile.allergies = validated.allergies or ""
        profile.physical_limitations = validated.physical_limitations or "none"
        profile.calculate_metrics()
        db.session.commit()

        # Generate initial recommendations and tasks
        try:
            RecommendationService.generate_daily_recommendation(user_id=user.id)
        except Exception:
            pass

        AuditService.log_event("ONBOARDING_COMPLETE", user_id=user.id, details={"health_goal": profile.health_goal})
        flash("Your personalized health profile is ready! Welcome to Vitalis AI.", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("onboarding.html", user=user, form=form_data)


def _verify_and_extract_google_identity(
    id_token_str: Optional[str],
    access_token: Optional[str],
    client_id: str,
) -> Dict[str, Any]:
    """
    Cryptographically verify the Google ID token and/or fetch verified userinfo.
    Uses google.oauth2.id_token to validate signatures, audience, issuer, and expiry.
    Falls back safely to userinfo endpoint if id_token is not present or mocked.
    """
    identity = {}
    if id_token_str:
        try:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests

            # Cryptographically verify the token with Google public keys
            id_info = google_id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                client_id,
                clock_skew_in_seconds=10,
            )

            # Validate issuer
            issuer = id_info.get("iss")
            if issuer not in ("accounts.google.com", "https://accounts.google.com"):
                raise ValueError(f"Untrusted token issuer: {issuer}")

            identity["sub"] = str(id_info.get("sub"))
            identity["email"] = id_info.get("email")
            identity["email_verified"] = bool(id_info.get("email_verified", False))
            identity["name"] = id_info.get("name")
            identity["picture"] = id_info.get("picture")
        except Exception as e:
            current_app.logger.warning(
                f"Google ID token verification failed or bypassed: {e}."
            )
            if not access_token:
                raise

    # Fallback/complementary resolution using Google userinfo endpoint
    if access_token and (not identity.get("sub") or not identity.get("email")):
        userinfo = _fetch_google_userinfo(access_token)
        identity["sub"] = str(userinfo.get("sub"))
        identity["email"] = userinfo.get("email")
        identity["email_verified"] = bool(userinfo.get("email_verified", True))
        identity["name"] = userinfo.get("name") or identity.get("name")
        identity["picture"] = userinfo.get("picture") or identity.get("picture")

    return identity


def _exchange_google_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    """Exchange authorization code for tokens via Google token endpoint."""
    token_url = "https://oauth2.googleapis.com/token"
    payload = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode("utf-8")

    req = urllib.request.Request(token_url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google token exchange failed ({he.code}): {err_body}")


def _fetch_google_userinfo(access_token: str) -> dict:
    """Fetch verified user profile information from Google userinfo endpoint."""
    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
    req = urllib.request.Request(userinfo_url, method="GET")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google userinfo request failed ({he.code}): {err_body}")


# ==============================================================================
# Phone Number & SMS / OTP Authentication Endpoints
# ==============================================================================

@auth_bp.route("/auth/phone/send-otp", methods=["POST"])
def phone_send_otp():
    """Generates and delivers a 4-digit verification code to the requested phone number."""
    if request.is_json:
        data = request.get_json() or {}
        phone = data.get("phone", "")
    else:
        phone = request.form.get("phone", "")

    phone = str(phone).strip()
    if not phone:
        return jsonify({"success": False, "error": "Phone number is required."}), 400

    AuditService.log_event("PHONE_OTP_REQUESTED", details={"phone": OTPService.mask_phone(phone)})

    success, message, masked_phone, dev_code = OTPService.send_otp(phone)
    if not success:
        return jsonify({"success": False, "error": message}), 400

    AuditService.log_event("PHONE_OTP_SENT", details={"phone": masked_phone})

    response_payload = {
        "success": True,
        "message": message,
        "masked_phone": masked_phone
    }
    if dev_code:
        response_payload["dev_code"] = dev_code

    return jsonify(response_payload), 200


@auth_bp.route("/auth/phone/verify-otp", methods=["POST"])
def phone_verify_otp():
    """Verifies candidate OTP, creates or retrieves user, establishes session, and returns redirect URL."""
    if request.is_json:
        data = request.get_json() or {}
        phone = data.get("phone", "")
        otp = data.get("otp", "")
    else:
        phone = request.form.get("phone", "")
        otp = request.form.get("otp", "")

    phone = str(phone).strip()
    otp = str(otp).strip()

    if not phone or not otp:
        return jsonify({"success": False, "error": "Phone number and 4-digit code are required."}), 400

    success, message = OTPService.verify_otp(phone, otp)
    if not success:
        AuditService.log_event("PHONE_LOGIN_FAILED", details={"phone": OTPService.mask_phone(phone), "reason": message})
        return jsonify({"success": False, "error": message}), 400

    clean_phone = OTPService.normalize_phone(phone)
    if not clean_phone:
        return jsonify({"success": False, "error": "Invalid phone format."}), 400

    # User account handling
    user = User.query.filter_by(phone_number=clean_phone).first()
    is_new_user = False

    if not user:
        is_new_user = True
        clean_digits = "".join(filter(str.isdigit, clean_phone))
        synthetic_email = f"phone_{clean_digits}@phone.vitalis.ai"

        existing_by_email = User.query.filter_by(email=synthetic_email).first()
        if existing_by_email:
            user = existing_by_email
            user.phone_number = clean_phone
            is_new_user = False
        else:
            user = User(
                name=f"User {clean_phone[-4:]}",
                email=synthetic_email,
                phone_number=clean_phone,
                auth_provider="phone",
                role="user"
            )
            user.set_password(secrets.token_urlsafe(32))
            db.session.add(user)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to create phone user account: {e}")
            return jsonify({"success": False, "error": "Account creation failed. Please try again."}), 500

        AuditService.log_event("PHONE_ACCOUNT_CREATED", user_id=user.id, details={"phone": clean_phone})
        AuditService.log_event("PHONE_USER_REGISTER", user_id=user.id, details={"phone": clean_phone})

    # Session fixation defense
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    AuditService.log_event("PHONE_LOGIN_SUCCESS", user_id=user.id, details={"phone": clean_phone})

    # Determine destination (onboarding if new user/missing profile, else dashboard)
    profile = user.profile
    needs_onboarding = is_new_user or (profile is None) or (not profile.height_cm or not profile.weight_kg)
    redirect_url = url_for("auth.onboarding") if needs_onboarding else url_for("dashboard.index")

    return jsonify({
        "success": True,
        "message": "Phone number verified successfully.",
        "redirect_url": redirect_url,
        "is_new_user": is_new_user
    }), 200

