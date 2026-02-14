from rest_framework.decorators import api_view, permission_classes, authentication_classes , parser_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth.hashers import check_password
from rest_framework.parsers import MultiPartParser, FormParser
# Models
from company.models import ServiceCenterRegister
from users.models import MyOrder, OrderComplaint, OrderFeedback, UserProfile, Contact, CancelDetails

# Serializers
from .serializers import (
    ServiceCenterSerializer, OrderSerializer, ComplaintSerializer, 
    FeedbackSerializer, CustomerSerializer, ContactSerializer, CancelledOrderSerializer
)
from django.conf import settings
from twilio.rest import Client
import random

# Models
from users.models import MyOrder
from servicecenter.models import ServiceCompletion
from .serializers import ServiceCompletionSerializer

# --- Helper Function ---
def get_service_center(request):
    user_id = request.GET.get('user_id') or request.data.get('user_id')
    if not user_id:
        return None
    try:
        return ServiceCenterRegister.objects.get(id=user_id)
    except ServiceCenterRegister.DoesNotExist:
        return None

# ================= 1. AUTHENTICATION (Register & Login) =================

@api_view(['POST'])
@authentication_classes([])  # 👈 YE IMPORTANT HAI (Auth Disable)
@permission_classes([AllowAny]) # 👈 YE IMPORTANT HAI (Public Access)
def register_servicecenter_api(request):
    if ServiceCenterRegister.objects.filter(username=request.data.get('username')).exists():
        return Response({'error': 'Username already taken'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ServiceCenterSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({'message': 'Registered Successfully', 'data': serializer.data}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login_servicecenter_api(request):
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response({'error': 'Please provide username and password'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = ServiceCenterRegister.objects.get(username=username)
        if check_password(password, user.password):
            return Response({
                'message': 'Login Successful',
                'user_id': user.id,
                'username': user.username,
                'district': user.district,
                'pincode': user.pincode
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid password'}, status=status.HTTP_401_UNAUTHORIZED)
    except ServiceCenterRegister.DoesNotExist:
        return Response({'error': 'Username not found'}, status=status.HTTP_404_NOT_FOUND)

# ================= 2. DASHBOARD & PROFILE =================

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def servicecenter_dashboard_api(request):
    servicecenter = get_service_center(request)
    if not servicecenter:
        return Response({'error': 'User ID required'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ServiceCenterSerializer(servicecenter)
    return Response(serializer.data)

@api_view(['GET', 'PUT'])
@authentication_classes([])
@permission_classes([AllowAny])
def servicecenter_profile_api(request):
    servicecenter = get_service_center(request)
    if not servicecenter:
        return Response({'error': 'Service Center ID required'}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'GET':
        serializer = ServiceCenterSerializer(servicecenter)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = ServiceCenterSerializer(servicecenter, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Profile Updated', 'data': serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ================= 3. ORDERS & COMPLAINTS =================

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def servicecenter_orders_api(request):
    servicecenter = get_service_center(request)
    if not servicecenter:
        return Response({'error': 'Service Center ID required'}, status=status.HTTP_400_BAD_REQUEST)

    district = servicecenter.district
    pincode = servicecenter.pincode

    orders = MyOrder.objects.filter(district__iexact=district, pincode=pincode).order_by("-created_at")
    
    complaints = OrderComplaint.objects.filter(
        user__userprofile__district__iexact=district,
        user__userprofile__pincode=pincode
    ).order_by("-created_at")

    data = {
        "orders": OrderSerializer(orders, many=True).data,
        "complaints": ComplaintSerializer(complaints, many=True).data,
        "counts": {
            "total": orders.count(),
            "accepted": orders.filter(status="accepted").count(),
            "rejected": orders.filter(status="rejected").count(),
            "pending": orders.filter(status="pending").count(),
        }
    }
    return Response(data)

# ================= 4. ORDER ACTIONS (Accept/Reject) =================

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def update_order_status_api(request, order_id):
    servicecenter = get_service_center(request)
    if not servicecenter:
        return Response({'error': 'Service Center ID required'}, status=status.HTTP_400_BAD_REQUEST)

    action = request.data.get('action') 
    
    try:
        order = MyOrder.objects.get(id=order_id, status="pending")
    except MyOrder.DoesNotExist:
        return Response({'error': 'Order not found or not pending'}, status=status.HTTP_404_NOT_FOUND)

    if action == 'accept':
        order.status = "accepted"
        order.service_center_id = servicecenter.id
        order.save()
        return Response({'message': 'Order Accepted Successfully'})
    
    elif action == 'reject':
        order.status = "rejected"
        order.save()
        return Response({'message': 'Order Rejected'})

    return Response({'error': 'Invalid Action'}, status=status.HTTP_400_BAD_REQUEST)

# ================= 5. CANCELLED ORDERS =================

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def service_cancel_orders_api(request):
    servicecenter = get_service_center(request)
    if not servicecenter:
        return Response({'error': 'Service Center ID required'}, status=status.HTTP_400_BAD_REQUEST)

    cancelled_ids = CancelDetails.objects.values_list("order_id", flat=True)
    cancelled_orders = MyOrder.objects.filter(
        id__in=cancelled_ids, 
        pincode=servicecenter.pincode
    ).order_by("-created_at")

    serializer = CancelledOrderSerializer(cancelled_orders, many=True)
    return Response(serializer.data)

# ================= 6. CUSTOMERS LIST =================

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def customers_list_api(request):
    servicecenter = get_service_center(request)
    if not servicecenter:
        return Response({'error': 'Service Center ID required'}, status=status.HTTP_400_BAD_REQUEST)

    customers = UserProfile.objects.filter(pincode=servicecenter.pincode)
    serializer = CustomerSerializer(customers, many=True)
    return Response(serializer.data)

# ================= 7. FEEDBACK & CONTACTS =================

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def feedback_contacts_api(request):
    servicecenter = get_service_center(request)
    if not servicecenter:
        return Response({'error': 'Service Center ID required'}, status=status.HTTP_400_BAD_REQUEST)

    feedbacks = OrderFeedback.objects.filter(pincode=servicecenter.pincode).order_by('-created_at')
    contacts = Contact.objects.filter(pincode=servicecenter.pincode).order_by("-created_at")

    data = {
        "feedbacks": FeedbackSerializer(feedbacks, many=True).data,
        "contacts": ContactSerializer(contacts, many=True).data
    }
    return Response(data)


# ================= 1. COMPLETE SERVICE (Upload Images & Send OTP) =================
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser]) # Essential for Image Upload
def api_complete_service(request, order_id):
    # 1. Get Service Center ID from request (App must send this)
    service_center_id = request.data.get('service_center_id')
    if not service_center_id:
        return Response({'error': 'Service Center ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    # 2. Get Order
    order = get_object_or_404(MyOrder, id=order_id)

    # 3. Create or Update ServiceCompletion Object
    service_obj, created = ServiceCompletion.objects.get_or_create(
        order=order,
        defaults={'service_center_id': service_center_id}
    )
    
    # 4. Save Images & ID
    if request.FILES.get('old_image'):
        service_obj.old_image = request.FILES['old_image']
    if request.FILES.get('new_image'):
        service_obj.new_image = request.FILES['new_image']
    
    service_obj.service_center_id = service_center_id
    
    # 5. Generate OTP
    otp = str(random.randint(100000, 999999))
    service_obj.otp = otp
    service_obj.save()

    # 6. Send OTP (Twilio)
    sms_status = "SMS Failed"
    try:
        if settings.TWILIO_ACCOUNT_SID:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=f"Your verification OTP is {otp}. Do not share it.",
                from_=settings.TWILIO_PHONE_NUMBER,
                to="+919555286398" # Replace with order.mobile in production
            )
            sms_status = "SMS Sent"
    except Exception as e:
        print(f"Twilio Error: {e}")

    return Response({
        'message': 'Images Uploaded & OTP Generated',
        'otp_debug': otp, # Remove this line in production!
        'sms_status': sms_status
    }, status=status.HTTP_200_OK)


# ================= 2. VERIFY OTP (Finalize Order) =================
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def api_verify_otp(request, order_id):
    entered_otp = request.data.get("otp")
    
    if not entered_otp:
        return Response({'error': 'OTP is required'}, status=status.HTTP_400_BAD_REQUEST)

    service_obj = get_object_or_404(ServiceCompletion, order_id=order_id)

    if service_obj.otp == entered_otp:
        # Mark Verified
        service_obj.otp_verified = True
        service_obj.save()

        # Update Main Order Status
        service_obj.order.status = "completed"
        service_obj.order.save()

        return Response({'message': 'Service Completed Successfully!'}, status=status.HTTP_200_OK)
    
    else:
        return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)