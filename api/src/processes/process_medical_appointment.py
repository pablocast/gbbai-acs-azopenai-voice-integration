# Copyright (c) Microsoft. All rights reserved.

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta

from semantic_kernel.functions import kernel_function
from semantic_kernel.processes import ProcessBuilder
from semantic_kernel.processes.kernel_process import KernelProcessStep, KernelProcessStepContext


@dataclass
class AppointmentData:
    patient_name: Optional[str] = None
    contact_number: Optional[str] = None
    specialty: Optional[str] = None
    insurance_type: Optional[str] = None
    clinic: Optional[str] = None
    doctor_name: Optional[str] = None
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    notification_preference: Optional[str] = None


class GreetingStep(KernelProcessStep):
    class Functions(Enum):
        InitialGreeting = "InitialGreeting"

    class OutputEvents(Enum):
        ServiceRequested = "ServiceRequested"

    @kernel_function(name=Functions.InitialGreeting)
    async def initial_greeting(self, context: KernelProcessStepContext):
        greeting = "Bienvenido(a) a la Red de Clínicas Bupa. ¿En qué podemos ayudarte hoy? ¿Desea agendar una hora médica, consultar una hora ya agendada, o necesita otra información?"
        print(f"GREETING: {greeting}")
        
        appointment_data = AppointmentData()
        await context.emit_event(
            process_event=GreetingStep.OutputEvents.ServiceRequested, 
            data=appointment_data
        )


class ServiceSelectionStep(KernelProcessStep):
    class Functions(Enum):
        SelectService = "SelectService"

    class OutputEvents(Enum):
        ScheduleAppointment = "ScheduleAppointment"
        CheckAppointment = "CheckAppointment"
        OtherInformation = "OtherInformation"

    @kernel_function(name=Functions.SelectService)
    async def select_service(self, context: KernelProcessStepContext, appointment_data: AppointmentData, service_type: str):
        print(f"SERVICE_SELECTION: Patient requested '{service_type}'")
        
        if service_type.lower() in ["agendar", "schedule", "nueva cita"]:
            await context.emit_event(
                process_event=ServiceSelectionStep.OutputEvents.ScheduleAppointment,
                data=appointment_data
            )
        elif service_type.lower() in ["consultar", "check", "verificar"]:
            await context.emit_event(
                process_event=ServiceSelectionStep.OutputEvents.CheckAppointment,
                data=appointment_data
            )
        else:
            await context.emit_event(
                process_event=ServiceSelectionStep.OutputEvents.OtherInformation,
                data=appointment_data
            )


class SpecialtySelectionStep(KernelProcessStep):
    class Functions(Enum):
        SelectSpecialty = "SelectSpecialty"

    class OutputEvents(Enum):
        SpecialtySelected = "SpecialtySelected"

    @kernel_function(name=Functions.SelectSpecialty)
    async def select_specialty(self, context: KernelProcessStepContext, appointment_data: AppointmentData, specialty: str, insurance_type: Optional[str] = None):
        print(f"SPECIALTY_SELECTION: Selected specialty '{specialty}', insurance: '{insurance_type}'")
        
        appointment_data.specialty = specialty
        appointment_data.insurance_type = insurance_type
        
        await context.emit_event(
            process_event=SpecialtySelectionStep.OutputEvents.SpecialtySelected,
            data=appointment_data
        )


class ClinicSelectionStep(KernelProcessStep):
    class Functions(Enum):
        SelectClinic = "SelectClinic"

    class OutputEvents(Enum):
        ClinicSelected = "ClinicSelected"

    @kernel_function(name=Functions.SelectClinic)
    async def select_clinic(self, context: KernelProcessStepContext, appointment_data: AppointmentData, clinic_name: str):
        print(f"CLINIC_SELECTION: Selected clinic '{clinic_name}'")
        
        appointment_data.clinic = clinic_name
        
        await context.emit_event(
            process_event=ClinicSelectionStep.OutputEvents.ClinicSelected,
            data=appointment_data
        )


class AvailabilitySearchStep(KernelProcessStep):
    class Functions(Enum):
        SearchAvailability = "SearchAvailability"

    class OutputEvents(Enum):
        AvailabilityFound = "AvailabilityFound"
        NoAvailability = "NoAvailability"

    @kernel_function(name=Functions.SearchAvailability)
    async def search_availability(self, context: KernelProcessStepContext, appointment_data: AppointmentData):
        print(f"AVAILABILITY_SEARCH: Searching for {appointment_data.specialty} at {appointment_data.clinic}")
        
        # Generate dynamic date - tomorrow at 11:00 AM
        tomorrow = datetime.now() + timedelta(days=1)
        appointment_data.doctor_name = "Dr. González"
        appointment_data.appointment_date = tomorrow.strftime("%Y-%m-%d")
        appointment_data.appointment_time = "11:00"
        
        # Format the date for display
        display_date = tomorrow.strftime("%d de %B del %Y")
        availability_message = f"Tenemos una hora disponible con el {appointment_data.doctor_name} el {display_date} a las {appointment_data.appointment_time}. ¿Le acomoda?"
        print(f"AVAILABILITY_FOUND: {availability_message}")
        
        await context.emit_event(
            process_event=AvailabilitySearchStep.OutputEvents.AvailabilityFound,
            data=appointment_data
        )


class PatientDataStep(KernelProcessStep):
    class Functions(Enum):
        CollectPatientData = "CollectPatientData"

    class OutputEvents(Enum):
        PatientDataCollected = "PatientDataCollected"

    @kernel_function(name=Functions.CollectPatientData)
    async def collect_patient_data(self, context: KernelProcessStepContext, appointment_data: AppointmentData, patient_name: str, contact_number: str, notification_preference: str):
        print(f"PATIENT_DATA: Collecting data for {patient_name}")
        
        appointment_data.patient_name = patient_name
        appointment_data.contact_number = contact_number
        appointment_data.notification_preference = notification_preference
        
        await context.emit_event(
            process_event=PatientDataStep.OutputEvents.PatientDataCollected,
            data=appointment_data
        )


class AppointmentConfirmationStep(KernelProcessStep):
    class Functions(Enum):
        ConfirmAppointment = "ConfirmAppointment"

    class OutputEvents(Enum):
        AppointmentConfirmed = "AppointmentConfirmed"

    @kernel_function(name=Functions.ConfirmAppointment)
    async def confirm_appointment(self, context: KernelProcessStepContext, appointment_data: AppointmentData):
        # Format the confirmation date for display
        appointment_datetime = datetime.strptime(appointment_data.appointment_date, "%Y-%m-%d")
        display_date = appointment_datetime.strftime("%d de %B del %Y")
        
        confirmation_message = f"Su hora ha sido agendada para el {display_date} a las {appointment_data.appointment_time} con el {appointment_data.doctor_name} en la Clínica {appointment_data.clinic}. Recibirá un mensaje de confirmación con los detalles."
        print(f"APPOINTMENT_CONFIRMED: {confirmation_message}")
        
        await context.emit_event(
            process_event=AppointmentConfirmationStep.OutputEvents.AppointmentConfirmed,
            data=appointment_data
        )


class ClosingStep(KernelProcessStep):
    class Functions(Enum):
        CloseCall = "CloseCall"

    class OutputEvents(Enum):
        CallClosed = "CallClosed"

    @kernel_function(name=Functions.CloseCall)
    async def close_call(self, context: KernelProcessStepContext, appointment_data: AppointmentData):
        closing_message = "¿Hay algo más en lo que podamos ayudarle? Gracias por llamar a la Red de Clínicas Bupa. Que tenga un buen día."
        print(f"CLOSING: {closing_message}")
        
        await context.emit_event(
            process_event=ClosingStep.OutputEvents.CallClosed,
            data=appointment_data
        )


class MedicalAppointmentProcess:
    class ProcessEvents(Enum):
        CallStarted = "CallStarted"
        CallCompleted = "CallCompleted"

    @staticmethod
    def create_process(process_name: str = "MedicalAppointmentProcess"):
        process_builder = ProcessBuilder(process_name)

        # Add steps
        greeting_step = process_builder.add_step(GreetingStep)
        service_selection_step = process_builder.add_step(ServiceSelectionStep)
        specialty_selection_step = process_builder.add_step(SpecialtySelectionStep)
        clinic_selection_step = process_builder.add_step(ClinicSelectionStep)
        availability_search_step = process_builder.add_step(AvailabilitySearchStep)
        patient_data_step = process_builder.add_step(PatientDataStep)
        appointment_confirmation_step = process_builder.add_step(AppointmentConfirmationStep)
        closing_step = process_builder.add_step(ClosingStep)

        # Define workflow connections with explicit parameter mapping
        process_builder.on_input_event(MedicalAppointmentProcess.ProcessEvents.CallStarted).send_event_to(greeting_step)

        greeting_step.on_event(GreetingStep.OutputEvents.ServiceRequested).send_event_to(
            service_selection_step.with_parameters(appointment_data="data", service_type=None)  # service_type will be provided by user input in the test
        )

        service_selection_step.on_event(ServiceSelectionStep.OutputEvents.ScheduleAppointment).send_event_to(
            specialty_selection_step.with_parameters(appointment_data="data", specialty=None, insurance_type=None)
        )

        specialty_selection_step.on_event(SpecialtySelectionStep.OutputEvents.SpecialtySelected).send_event_to(
            clinic_selection_step.with_parameters(appointment_data="data", clinic_name=None)
        )

        clinic_selection_step.on_event(ClinicSelectionStep.OutputEvents.ClinicSelected).send_event_to(
            availability_search_step.with_parameters(appointment_data="data")
        )

        availability_search_step.on_event(AvailabilitySearchStep.OutputEvents.AvailabilityFound).send_event_to(
            patient_data_step.with_parameters(appointment_data="data", patient_name=None, contact_number=None, notification_preference=None)
        )

        patient_data_step.on_event(PatientDataStep.OutputEvents.PatientDataCollected).send_event_to(
            appointment_confirmation_step.with_parameters(appointment_data="data")
        )

        appointment_confirmation_step.on_event(AppointmentConfirmationStep.OutputEvents.AppointmentConfirmed).send_event_to(
            closing_step.with_parameters(appointment_data="data")
        )

        return process_builder

