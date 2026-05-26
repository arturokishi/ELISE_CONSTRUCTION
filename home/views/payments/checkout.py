import stripe
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import json

from home.models import QuoteRequest, Payment, Conversation

stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
@require_POST
def create_checkout_session(request):
    try:
        data = json.loads(request.body)
        quote_id = data.get('quote_id')

        if not quote_id:
            return JsonResponse({'error': 'quote_id is required'}, status=400)

        try:
            quote = QuoteRequest.objects.select_related(
                'supplier__supplier_profile',
                'conversation',
                'client'
            ).get(id=quote_id)
        except QuoteRequest.DoesNotExist:
            return JsonResponse({'error': 'Quote not found'}, status=404)

        if quote.client != request.user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        if quote.status != 'quoted':
            return JsonResponse({'error': 'Quote is not in quoted status'}, status=400)

        if quote.payment_status == 'paid':
            return JsonResponse({'error': 'This quote has already been paid'}, status=400)

        if not quote.quoted_price:
            return JsonResponse({'error': 'Quote has no price set'}, status=400)

        try:
            supplier_profile = quote.supplier.supplier_profile
        except Exception:
            return JsonResponse({'error': 'Supplier profile not found'}, status=400)

        if not supplier_profile.stripe_account_id:
            return JsonResponse({
                'error': 'Este proveedor aún no ha conectado su cuenta de Stripe.'
            }, status=400)

        amount_total = int(quote.quoted_price * 100)
        fee_percent = supplier_profile.platform_fee_percent
        application_fee = int(amount_total * fee_percent / 100)
        supplier_payout = amount_total - application_fee

        base_url = settings.SITE_URL
        success_url = f"{base_url}/payments/success/?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/chat/?conversation={quote.conversation_id}"

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': amount_total,
                    'product_data': {
                        'name': quote.product_name,
                        'description': f"Cotización #{quote.id} — {quote.supplier.get_full_name() or quote.supplier.username}",
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            payment_intent_data={
                'application_fee_amount': application_fee,
                'transfer_data': {
                    'destination': supplier_profile.stripe_account_id,
                },
            },
            metadata={
                'quote_id': quote.id,
                'buyer_id': request.user.id,
                'supplier_id': quote.supplier.id,
                'conversation_id': quote.conversation_id,
            }
        )

        Payment.objects.create(
            quote=quote,
            buyer=request.user,
            supplier=quote.supplier,
            conversation=quote.conversation,
            amount_total=amount_total,
            application_fee=application_fee,
            supplier_payout=supplier_payout,
            stripe_checkout_session_id=session.id,
            status='pending',
        )

        quote.payment_status = 'pending'
        quote.save(update_fields=['payment_status'])

        return JsonResponse({'checkout_url': session.url})

    except stripe.error.StripeError as e:
        return JsonResponse({'error': str(e.user_message)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def payment_success(request):
    session_id = request.GET.get('session_id')
    payment = None

    if session_id:
        try:
            payment = Payment.objects.select_related(
                'quote', 'supplier'
            ).get(stripe_checkout_session_id=session_id)
        except Payment.DoesNotExist:
            pass

    return render(request, 'home/payments/success.html', {
        'payment': payment,
    })