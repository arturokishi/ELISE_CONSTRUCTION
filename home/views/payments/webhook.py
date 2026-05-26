import stripe
import json
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from home.models import Payment, QuoteRequest

stripe.api_key = settings.STRIPE_SECRET_KEY


@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    # 1. Verify the request actually came from Stripe
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Invalid payload
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError:
        # Invalid signature — not from Stripe
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    # 2. Handle the events we care about
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        _handle_checkout_completed(session)

    elif event['type'] == 'checkout.session.expired':
        session = event['data']['object']
        _handle_checkout_expired(session)

    # Always return 200 to Stripe so it stops retrying
    return JsonResponse({'status': 'ok'})


def _handle_checkout_completed(session):
    session_id = session.get('id')
    payment_intent_id = session.get('payment_intent', '')

    try:
        payment = Payment.objects.select_related('quote').get(
            stripe_checkout_session_id=session_id
        )
    except Payment.DoesNotExist:
        print(f"WEBHOOK ERROR: Payment not found for session {session_id}")
        return

    # Update Payment — this is the ONLY place status becomes 'paid'
    payment.status = 'paid'
    payment.stripe_payment_intent_id = payment_intent_id or ''
    payment.save(update_fields=['status', 'stripe_payment_intent_id'])

    # Update the QuoteRequest
    quote = payment.quote
    quote.payment_status = 'paid'
    quote.save(update_fields=['payment_status'])

    print(f"WEBHOOK: Payment #{payment.id} confirmed for quote #{quote.id}")


def _handle_checkout_expired(session):
    session_id = session.get('id')

    try:
        payment = Payment.objects.select_related('quote').get(
            stripe_checkout_session_id=session_id
        )
    except Payment.DoesNotExist:
        return

    # Session expired — reset both records so buyer can try again
    payment.status = 'failed'
    payment.save(update_fields=['status'])

    quote = payment.quote
    quote.payment_status = 'unpaid'
    quote.save(update_fields=['payment_status'])

    print(f"WEBHOOK: Session expired for payment #{payment.id}, quote reset to unpaid")