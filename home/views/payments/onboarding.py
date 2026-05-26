import stripe
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

from home.models import Supplier

stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
def supplier_onboarding(request):
    """
    Generates a Stripe Connect Express onboarding link for the supplier.
    The supplier clicks this and gets taken to Stripe's hosted onboarding form.
    """
    # Only suppliers can onboard
    if request.user.userprofile.role != 'supplier':
        return JsonResponse({'error': 'Only suppliers can onboard'}, status=403)

    try:
        supplier = request.user.supplier_profile
    except Supplier.DoesNotExist:
        return JsonResponse({'error': 'Supplier profile not found'}, status=404)

    # If they already have a Stripe account, generate a new link
    # in case they didn't finish onboarding the first time
    if not supplier.stripe_account_id:
        # Create a new Express account for this supplier
        account = stripe.Account.create(
            type='express',
            email=request.user.email,
            capabilities={
                'card_payments': {'requested': True},
                'transfers': {'requested': True},
            },
            business_type='individual',
            metadata={
                'user_id': request.user.id,
                'username': request.user.username,
            }
        )
        supplier.stripe_account_id = account.id
        supplier.save(update_fields=['stripe_account_id'])

    # Generate the onboarding link
    base_url = settings.SITE_URL
    account_link = stripe.AccountLink.create(
        account=supplier.stripe_account_id,
        refresh_url=f"{base_url}/supplier/connect/onboarding/",
        return_url=f"{base_url}/supplier/connect/return/",
        type='account_onboarding',
    )

    return redirect(account_link.url)


@login_required
def supplier_onboarding_return(request):
    """
    Stripe redirects the supplier here after they finish onboarding.
    We verify their account status and update the database.
    """
    if request.user.userprofile.role != 'supplier':
        return redirect('home:home')

    try:
        supplier = request.user.supplier_profile
    except Supplier.DoesNotExist:
        return redirect('home:home')

    if not supplier.stripe_account_id:
        return redirect('home:home')

    # Check account status with Stripe
    try:
        account = stripe.Account.retrieve(supplier.stripe_account_id)
        charges_enabled = account.charges_enabled
        details_submitted = account.details_submitted
    except stripe.error.StripeError:
        charges_enabled = False
        details_submitted = False

    return render(request, 'home/payments/onboarding_return.html', {
        'charges_enabled': charges_enabled,
        'details_submitted': details_submitted,
        'supplier': supplier,
    })