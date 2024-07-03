from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail, BadHeaderError
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.utils.html import strip_tags
from .models import Payment
from hospital.models import Patient
from pharmacy.models import Order
from doctor.models import Appointment
from django.conf import settings
from sslcommerz_lib import SSLCOMMERZ
import random
import string

# SSLCOMMERZ configuration from settings
STORE_ID = settings.STORE_ID
STORE_PASSWORD = settings.STORE_PASSWORD

payment_settings = {
    'store_id': STORE_ID,
    'store_pass': STORE_PASSWORD,
    'issandbox': True  # Adjust based on your environment
}

sslcz = SSLCOMMERZ(payment_settings)

# Utility functions
def generate_random_string():
    N = 8
    return "SSLCZ_TEST_" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=N))

def generate_random_invoice():
    N = 4
    return "#INV-" + ''.join(random.choices(string.digits, k=N))

def payment_home(request):
    return render(request, 'index.html')

@csrf_exempt
def ssl_payment_request(request, pk, id):
    try:
        patient = Patient.objects.get(patient_id=pk)
        appointment = Appointment.objects.get(id=id)
        
        invoice_number = generate_random_invoice()
        
        post_body = {
            'total_amount': appointment.doctor.consultation_fee + appointment.doctor.report_fee,
            'currency': "INR",
            'tran_id': generate_random_string(),
            'success_url': request.build_absolute_uri(reverse('ssl-payment-success')),
            'fail_url': request.build_absolute_uri(reverse('ssl-payment-fail')),
            'cancel_url': request.build_absolute_uri(reverse('ssl-payment-cancel')),
            'emi_option': 0,
            'cus_name': patient.username,
            'cus_email': patient.email,
            'cus_phone': patient.phone_number,
            'cus_add1': patient.address,
            'cus_city': "Pune",
            'cus_country': "India",
            'shipping_method': "NO",
            'num_of_item': 1,
            'product_name': "Test",
            'product_category': "Test Category",
            'product_profile': "general",
        }

        appointment.transaction_id = post_body['tran_id']
        appointment.save()

        payment = Payment.objects.create(
            patient=patient,
            appointment=appointment,
            name=post_body['cus_name'],
            email=post_body['cus_email'],
            phone=post_body['cus_phone'],
            address=post_body['cus_add1'],
            city=post_body['cus_city'],
            country=post_body['cus_country'],
            transaction_id=post_body['tran_id'],
            consulation_fee=appointment.doctor.consultation_fee,
            report_fee=appointment.doctor.report_fee,
            invoice_number=invoice_number,
            payment_type="appointment"
        )

        response = sslcz.createSession(post_body)
        print(response)

        return redirect(response['GatewayPageURL'])

    except Exception as e:
        print(e)
        return redirect('ssl-payment-fail')

@csrf_exempt
def ssl_payment_success(request):
    try:
        payment_data = request.POST
        status = payment_data['status']

        if status == 'VALID':
            tran_id = payment_data['tran_id']
            payment = Payment.objects.get(transaction_id=tran_id)
            payment_type = payment.payment_type

            if payment_type == "appointment":
                payment.val_transaction_id = payment_data['val_id']
                payment.currency_amount = payment_data['currency_amount']
                payment.card_type = payment_data['card_type']
                payment.card_no = payment_data['card_no']
                payment.bank_transaction_id = payment_data['bank_tran_id']
                payment.status = payment_data['status']
                payment.transaction_date = payment_data['tran_date']
                payment.currency = payment_data['currency']
                payment.card_issuer = payment_data['card_issuer']
                payment.card_brand = payment_data['card_brand']
                payment.save()

                appointment = Appointment.objects.get(transaction_id=tran_id)
                appointment.transaction_id = tran_id
                appointment.payment_status = "VALID"
                appointment.save()

                if sslcz.hash_validate_ipn(payment_data):
                    response = sslcz.validationTransactionOrder(payment_data['val_id'])
                    print(response)
                else:
                    print("Hash validation failed")

                # Mailtrap
                patient_email = payment.patient.email
                patient_name = payment.patient.name
                patient_username = payment.patient.username
                patient_phone_number = payment.patient.phone_number
                doctor_name = appointment.doctor.name

                subject = "Payment Receipt for appointment"

                values = {
                    "email": patient_email,
                    "name": patient_name,
                    "username": patient_username,
                    "phone_number": patient_phone_number,
                    "doctor_name": doctor_name,
                    "tran_id": payment_data['tran_id'],
                    "currency_amount": payment_data['currency_amount'],
                    "card_type": payment_data['card_type'],
                    "bank_transaction_id": payment_data['bank_tran_id'],
                    "transaction_date": payment_data['tran_date'],
                    "card_issuer": payment_data['card_issuer'],
                }

                html_message = render_to_string('appointment_mail_payment_template.html', {'values': values})
                plain_message = strip_tags(html_message)

                try:
                    send_mail(subject, plain_message, 'hospital_admin@gmail.com', [patient_email], html_message=html_message, fail_silently=False)
                except BadHeaderError:
                    return HttpResponse('Invalid header found')

                return redirect('patient-dashboard')

        elif status == 'FAILED':
            return redirect('ssl-payment-fail')

    except Exception as e:
        print(e)
        return redirect('ssl-payment-fail')

@csrf_exempt
def ssl_payment_fail(request):
    return render(request, 'fail.html')

@csrf_exempt
def ssl_payment_cancel(request):
    return render(request, 'cancel.html')

@csrf_exempt
def ssl_payment_request_medicine(request, pk, id):
    try:
        # Example logic to fetch necessary data
        patient = Patient.objects.get(pk=pk)
        order = Order.objects.get(pk=id)

        # Example context data
        context = {
            'patient': patient,
            'order': order,
        }

        return render(request, 'Pharmacy/checkout.html', context)

    except Patient.DoesNotExist or Order.DoesNotExist:
        return HttpResponse("Patient or Order not found")

@csrf_exempt
def ssl_payment_request_test(request, pk, id, pk2):
    try:
        # Example logic to fetch necessary data
        patient = Patient.objects.get(pk=pk)
        test_order = TestOrder.objects.get(pk=pk2)

        # Example context data
        context = {
            'patient': patient,
            'test_order': test_order,
        }

        return render(request, 'test_payment.html', context)

    except Patient.DoesNotExist or TestOrder.DoesNotExist:
        return HttpResponse("Patient or TestOrder not found")

@csrf_exempt
def payment_testing(request, pk):
    # Your testing view logic here
    return render(request, 'testing.html', context)
