#!/usr/bin/env python3
"""
Medical Appointment Process Runner with User Input
This script runs the actual Semantic Kernel medical appointment process with user interaction.
"""

import asyncio
import os
from enum import Enum
from typing import ClassVar
from dotenv import load_dotenv

from pydantic import Field
from semantic_kernel import Kernel
from semantic_kernel.kernel_pydantic import KernelBaseModel
from semantic_kernel.processes.kernel_process.kernel_process_step import KernelProcessStep
from semantic_kernel.processes.kernel_process.kernel_process_step_context import KernelProcessStepContext
from semantic_kernel.processes.kernel_process.kernel_process_step_state import KernelProcessStepState
from semantic_kernel.processes.local_runtime.local_event import KernelProcessEvent
from semantic_kernel.processes.local_runtime.local_kernel_process import start
from semantic_kernel.processes.process_builder import ProcessBuilder
from semantic_kernel.functions import kernel_function
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents import ChatHistory
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase

from process_medical_appointment import (
    AppointmentData,
    GreetingStep,
    ServiceSelectionStep,
    SpecialtySelectionStep,
    ClinicSelectionStep,
    AvailabilitySearchStep,
    PatientDataStep,
    AppointmentConfirmationStep
)

load_dotenv(override=True)


class MedicalAppointmentEvents(Enum):
    StartProcess = "StartProcess"
    UserInputReceived = "UserInputReceived"
    IntentIdentified = "IntentIdentified"
    ServiceIdentified = "ServiceIdentified"
    ContinueToNextStep = "ContinueToNextStep"
    SpecialtySelected = "SpecialtySelected"
    ClinicSelected = "ClinicSelected"
    AvailabilityFound = "AvailabilityFound"
    PatientDataCollected = "PatientDataCollected"
    AppointmentConfirmed = "AppointmentConfirmed"
    ProcessComplete = "ProcessComplete"
    Exit = "Exit"


class IntentRecognitionState(KernelBaseModel):
    """State for intent recognition step"""
    pass


class IntentRecognitionStep(KernelProcessStep[IntentRecognitionState]):
    """Step that uses chat completion to identify user intent"""
    IDENTIFY_INTENT: ClassVar[str] = "identify_intent"
    
    def create_default_state(self) -> IntentRecognitionState:
        return IntentRecognitionState()

    async def activate(self, state: KernelProcessStepState[IntentRecognitionState]):
        self.state = state.state or self.create_default_state()

    @kernel_function(name=IDENTIFY_INTENT)
    async def identify_intent(self, context: KernelProcessStepContext, data: dict):
        """Uses chat completion to identify user intent"""
        
        # Extract user input from the data
        user_input = data.get("user_input", "")
        if not user_input:
            print("⚠️ No user input provided")
            # Use fallback method
            intent = self._fallback_intent_detection("")
            service_type = "otro"
        else:
            # Try to use AI for intent recognition - for now, use fallback method
            # TODO: Implement proper AI integration when kernel access is available
            print(f"🤖 Analyzing user input: {user_input}")
            intent = self._fallback_intent_detection(user_input)
        
        print(f"🤖 Intent identificado: {intent}")
        
        # Map to service type for compatibility
        service_type_mapping = {
            "book_appointment": "agendar",
            "check_appointment": "consultar", 
            "other_information": "otro"
        }
        
        service_type = service_type_mapping.get(intent, "otro")
        
        # Emit intent identified event
        await context.emit_event(
            process_event=MedicalAppointmentEvents.IntentIdentified,
            data={"intent": intent, "service_type": service_type, "user_input": user_input}
        )
    
    def _fallback_intent_detection(self, user_input: str) -> str:
        """Fallback intent detection using simple text matching"""
        normalized = user_input.lower()
        if any(word in normalized for word in ["agendar", "nueva", "cita", "hora", "médica", "doctor", "reservar"]):
            return "book_appointment"
        elif any(word in normalized for word in ["consultar", "ver", "check", "agendada", "programada", "revisar"]):
            return "check_appointment"
        else:
            return "other_information"


class UserInputState(KernelBaseModel):
    current_step: str = "greeting"
    appointment_data: AppointmentData = Field(default_factory=AppointmentData)
    service_type: str = "otro"
    user_input: str = ""


class MedicalAppointmentUserInputStep(KernelProcessStep[UserInputState]):
    GET_USER_INPUT: ClassVar[str] = "get_user_input"
    CONTINUE_TO_NEXT_STEP: ClassVar[str] = "continue_to_next_step"

    def create_default_state(self) -> UserInputState:
        return UserInputState()

    async def activate(self, state: KernelProcessStepState[UserInputState]):
        self.state = state.state or self.create_default_state()

    @kernel_function(name=CONTINUE_TO_NEXT_STEP)
    async def continue_to_next_step(self, context: KernelProcessStepContext, data: dict):
        """Handles continuation to the next step"""
        next_step = data.get("next_step", "greeting")
        appointment_data = data.get("appointment_data", AppointmentData())
        
        print(f"🔄 Continuando a: {next_step}")
        
        # Update state
        self.state.current_step = next_step
        self.state.appointment_data = appointment_data
        
        # Trigger the get_user_input function to continue with the new step
        await self.get_user_input(context)

    @kernel_function(name=GET_USER_INPUT)
    async def get_user_input(self, context: KernelProcessStepContext):
        if not self.state:
            raise ValueError("State has not been initialized")

        # Get user input based on current step
        if self.state.current_step == "greeting":
            print("\n🏥 BIENVENIDO A LA RED DE CLÍNICAS BUPA")
            print("¿En qué podemos ayudarte hoy?")
            print("Puedes decir algo como:")
            print("• 'Quiero agendar una hora médica'")
            print("• 'Necesito consultar mi cita'") 
            print("• 'Quiero información sobre especialidades'")
            print("(También puedes escribir 'exit' para salir)")
            
            user_input = input("\n👤 Su respuesta: ").strip()
            
            if "exit" in user_input.lower():
                await context.emit_event(process_event=MedicalAppointmentEvents.Exit, data=None)
                return
            
            # Send user input to intent recognition step
            self.state.current_step = "intent_recognition"
            
            await context.emit_event(
                process_event=MedicalAppointmentEvents.UserInputReceived,
                data={"user_input": user_input, "appointment_data": self.state.appointment_data}
            )

        elif self.state.current_step == "specialty_selection":
            print("\n🏥 SELECCIÓN DE ESPECIALIDAD")
            specialties = [
                "Medicina General", "Cardiología", "Dermatología",
                "Ginecología", "Pediatría", "Traumatología", "Oftalmología", "Psiquiatría"
            ]
            
            print("Especialidades disponibles:")
            for i, specialty in enumerate(specialties, 1):
                print(f"  {i}. {specialty}")
            
            specialty_input = input("\n👤 ¿Con qué especialista desea atenderse? (número o nombre): ").strip()
            insurance_input = input("👤 ¿Es atención por Fonasa, Isapre o particular? (opcional): ").strip()
            
            # Parse specialty
            selected_specialty = self._parse_specialty_choice(specialty_input, specialties)
            self.state.appointment_data.specialty = selected_specialty
            self.state.appointment_data.insurance_type = insurance_input if insurance_input else None
            self.state.current_step = "clinic_selection"
            
            await context.emit_event(
                process_event=MedicalAppointmentEvents.SpecialtySelected,
                data={"appointment_data": self.state.appointment_data, "specialty": selected_specialty, "insurance_type": insurance_input or None}
            )

        elif self.state.current_step == "clinic_selection":
            print("\n🏢 SELECCIÓN DE CLÍNICA")
            clinics = [
                "Clínica Bupa Santiago Centro", "Clínica Bupa Las Condes",
                "Clínica Bupa Providencia", "Clínica Bupa Ñuñoa", "Clínica Bupa Valparaíso"
            ]
            
            print("Clínicas disponibles:")
            for i, clinic in enumerate(clinics, 1):
                print(f"  {i}. {clinic}")
            
            clinic_input = input("\n👤 ¿En cuál clínica desea atenderse? (número o nombre): ").strip()
            
            # Parse clinic
            selected_clinic = self._parse_clinic_choice(clinic_input, clinics)
            self.state.appointment_data.clinic = selected_clinic
            self.state.current_step = "availability_search"
            
            await context.emit_event(
                process_event=MedicalAppointmentEvents.ClinicSelected,
                data={"appointment_data": self.state.appointment_data, "clinic_name": selected_clinic}
            )

        elif self.state.current_step == "availability_confirmation":
            confirmation = input("\n👤 ¿Le acomoda esta fecha y hora? (sí/no): ").strip()
            
            if confirmation.lower() in ["sí", "si", "yes", "y"]:
                self.state.current_step = "patient_data"
                await context.emit_event(
                    process_event=MedicalAppointmentEvents.AvailabilityFound,
                    data=self.state.appointment_data
                )
            else:
                print("🤖 Entendido. Normalmente buscaríamos otras fechas disponibles.")
                await context.emit_event(process_event=MedicalAppointmentEvents.Exit, data=None)

        elif self.state.current_step == "patient_data":
            print("\n👤 DATOS DEL PACIENTE")
            print("Necesitamos algunos datos para confirmar su cita:")
            
            patient_name = input("👤 ¿Cuál es su nombre completo?: ").strip()
            contact_number = input("👤 ¿Cuál es su número de contacto?: ").strip()
            
            print("\nOpciones de notificación:")
            print("  1. SMS")
            print("  2. Email") 
            print("  3. Ambos")
            print("  4. Ninguno")
            
            notification_input = input("👤 ¿Cómo desea recibir recordatorios? (número o nombre): ").strip()
            notification_preference = self._parse_notification_choice(notification_input)
            
            self.state.appointment_data.patient_name = patient_name
            self.state.appointment_data.contact_number = contact_number
            self.state.appointment_data.notification_preference = notification_preference
            self.state.current_step = "confirmation"
            
            await context.emit_event(
                process_event=MedicalAppointmentEvents.PatientDataCollected,
                data={"appointment_data": self.state.appointment_data, "patient_name": patient_name, "contact_number": contact_number, "notification_preference": notification_preference}
            )

        elif self.state.current_step == "closing":
            additional_help = input("\n👤 ¿Necesita ayuda adicional? (sí/no): ").strip()
            
            if additional_help.lower() in ["sí", "si", "yes", "y"]:
                help_request = input("👤 ¿En qué más podemos ayudarle?: ").strip()
                print(f"🤖 Hemos registrado su consulta: {help_request}")
            
            print("🤖 Gracias por llamar a la Red de Clínicas Bupa. Que tenga un buen día.")
            await context.emit_event(process_event=MedicalAppointmentEvents.ProcessComplete, data=None)

    def _parse_specialty_choice(self, choice: str, specialties: list) -> str:
        """Parse specialty choice from user input"""
        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(specialties):
                return specialties[choice_num - 1]
        except ValueError:
            pass
        return choice

    def _parse_clinic_choice(self, choice: str, clinics: list) -> str:
        """Parse clinic choice from user input"""
        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(clinics):
                return clinics[choice_num - 1]
        except ValueError:
            pass
        return choice

    def _parse_notification_choice(self, choice: str) -> str:
        """Parse notification preference from user input"""
        options = ["SMS", "Email", "Ambos", "Ninguno"]
        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(options):
                return options[choice_num - 1]
        except ValueError:
            pass
        return choice


class MedicalAppointmentCoordinatorStep(KernelProcessStep):
    """Coordinates the flow between user input and medical appointment steps"""
    
    @kernel_function
    async def route_to_greeting(self, context: KernelProcessStepContext):
        """Routes to greeting step"""
        greeting_step = GreetingStep()
        mock_context = MockKernelProcessStepContext()
        
        # Execute greeting step
        await greeting_step.initial_greeting(mock_context)
    
    @kernel_function
    async def handle_intent_identification(self, context: KernelProcessStepContext, intent_data: dict):
        """Handles the result of intent identification"""
        intent = intent_data.get("intent", "other_information")
        service_type = intent_data.get("service_type", "otro")
        user_input = intent_data.get("user_input", "")
        
        print(f"🎯 Intent procesado: {intent} -> {service_type}")
        
        # Return service data for the next step (this will automatically route to service selection)
        return {"service_type": service_type, "appointment_data": AppointmentData(), "intent": intent}
        
    @kernel_function
    async def continue_to_specialty_selection(self, context: KernelProcessStepContext):
        """Sets the user input step to continue to specialty selection"""
        print("🔄 Preparando selección de especialidad...")
        # This will trigger the user input step to show specialty selection

    @kernel_function
    async def handle_service_selection(self, context: KernelProcessStepContext, service_data: dict):
        """Handles service selection"""
        service_step = ServiceSelectionStep()
        mock_context = MockKernelProcessStepContext()
        
        await service_step.select_service(
            mock_context,
            appointment_data=service_data["appointment_data"],
            service_type=service_data["service_type"]
        )
        
        # Route based on service type
        if service_data["service_type"] == "agendar":
            # Emit event to continue to specialty selection
            await context.emit_event(
                process_event=MedicalAppointmentEvents.ContinueToNextStep,
                data={"next_step": "specialty_selection", "appointment_data": service_data.get("appointment_data", AppointmentData())}
            )
        else:
            print("🤖 Funcionalidad de consulta o información no implementada en esta demo.")
            await context.emit_event(process_event=MedicalAppointmentEvents.Exit, data=None)

    @kernel_function
    async def handle_specialty_selection(self, context: KernelProcessStepContext, specialty_data: dict):
        """Handles specialty selection"""
        specialty_step = SpecialtySelectionStep()
        mock_context = MockKernelProcessStepContext()
        
        await specialty_step.select_specialty(
            mock_context,
            appointment_data=specialty_data["appointment_data"],
            specialty=specialty_data["specialty"],
            insurance_type=specialty_data["insurance_type"]
        )
        
        # Will trigger user input step to show clinic selection

    @kernel_function
    async def handle_clinic_selection(self, context: KernelProcessStepContext, clinic_data: dict):
        """Handles clinic selection"""
        clinic_step = ClinicSelectionStep()
        mock_context = MockKernelProcessStepContext()
        
        await clinic_step.select_clinic(
            mock_context,
            appointment_data=clinic_data["appointment_data"],
            clinic_name=clinic_data["clinic_name"]
        )
        
        # Route to availability search
        availability_step = AvailabilitySearchStep()
        availability_context = MockKernelProcessStepContext()
        
        await availability_step.search_availability(
            availability_context,
            appointment_data=clinic_data["appointment_data"]
        )
        
        # Will trigger user input step to show availability confirmation

    @kernel_function
    async def handle_availability_selection(self, context: KernelProcessStepContext, availability_data: dict):
        """Handles availability/time slot selection"""
        # Process the selected time slot here if needed
        print(f"⏰ Availability selected: {availability_data}")
        # This will trigger the user input step to continue to patient data collection

    @kernel_function
    async def handle_patient_data(self, context: KernelProcessStepContext, patient_data: dict):
        """Handles patient data collection"""
        patient_step = PatientDataStep()
        mock_context = MockKernelProcessStepContext()
        
        await patient_step.collect_patient_data(
            mock_context,
            appointment_data=patient_data["appointment_data"],
            patient_name=patient_data["patient_name"],
            contact_number=patient_data["contact_number"],
            notification_preference=patient_data["notification_preference"]
        )
        
        # Route to confirmation
        confirmation_step = AppointmentConfirmationStep()
        confirmation_context = MockKernelProcessStepContext()
        
        await confirmation_step.confirm_appointment(
            confirmation_context,
            appointment_data=patient_data["appointment_data"]
        )
        
        # Will trigger user input step to show closing


class MockKernelProcessStepContext:
    """Mock context for testing process steps"""
    def __init__(self):
        self.events = []
        self.data = None
    
    async def emit_event(self, process_event, data=None):
        self.events.append({"event": process_event, "data": data})
        self.data = data


async def run_medical_appointment_process():
    """Run the medical appointment process with user interaction"""
    kernel = Kernel()
    
    # Add Azure OpenAI chat completion service
    azure_openai_chat_service = AzureChatCompletion(
        service_id="default",
        deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
        endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
    )
    kernel.add_service(azure_openai_chat_service)
    
    # Build the process
    process = ProcessBuilder(name="MedicalAppointmentProcess")
    
    # Add steps
    coordinator_step = process.add_step(MedicalAppointmentCoordinatorStep)
    user_input_step = process.add_step(MedicalAppointmentUserInputStep)
    intent_recognition_step = process.add_step(IntentRecognitionStep)
    
    # Define the workflow
    process.on_input_event(event_id=MedicalAppointmentEvents.StartProcess).send_event_to(
        target=coordinator_step, function_name="route_to_greeting"
    )
    
    # Route from coordinator to user input
    coordinator_step.on_function_result(function_name="route_to_greeting").send_event_to(
        target=user_input_step, function_name="get_user_input"
    )
    
    # Route user input to intent recognition
    user_input_step.on_event(event_id=MedicalAppointmentEvents.UserInputReceived).send_event_to(
        target=intent_recognition_step, function_name="identify_intent", parameter_name="data"
    )
    
    # Route intent recognition result back to coordinator
    intent_recognition_step.on_event(event_id=MedicalAppointmentEvents.IntentIdentified).send_event_to(
        target=coordinator_step, function_name="handle_intent_identification", parameter_name="intent_data"
    )
    
    # Handle coordinator routing from intent identification to service selection
    coordinator_step.on_function_result(function_name="handle_intent_identification").send_event_to(
        target=coordinator_step, function_name="handle_service_selection", parameter_name="service_data"
    )
    
    # Route continue event to user input step
    coordinator_step.on_event(event_id=MedicalAppointmentEvents.ContinueToNextStep).send_event_to(
        target=user_input_step, function_name="continue_to_next_step", parameter_name="data"
    )
    
    # Handle other user input events (after intent has been processed)
    user_input_step.on_event(event_id=MedicalAppointmentEvents.SpecialtySelected).send_event_to(
        target=coordinator_step, function_name="handle_specialty_selection", parameter_name="specialty_data"
    )
    
    user_input_step.on_event(event_id=MedicalAppointmentEvents.ClinicSelected).send_event_to(
        target=coordinator_step, function_name="handle_clinic_selection", parameter_name="clinic_data"
    )
    
    user_input_step.on_event(event_id=MedicalAppointmentEvents.AvailabilityFound).send_event_to(
        target=coordinator_step, function_name="handle_availability_selection", parameter_name="availability_data"
    )
    
    user_input_step.on_event(event_id=MedicalAppointmentEvents.PatientDataCollected).send_event_to(
        target=coordinator_step, function_name="handle_patient_data", parameter_name="patient_data"
    )
    
    # Route back to user input from coordinator functions
    coordinator_step.on_function_result(function_name="handle_service_selection").send_event_to(
        target=user_input_step, function_name="get_user_input"
    )
    
    coordinator_step.on_function_result(function_name="handle_specialty_selection").send_event_to(
        target=user_input_step, function_name="get_user_input"
    )
    
    coordinator_step.on_function_result(function_name="handle_clinic_selection").send_event_to(
        target=user_input_step, function_name="get_user_input"
    )
    
    coordinator_step.on_function_result(function_name="handle_availability_selection").send_event_to(
        target=user_input_step, function_name="get_user_input"
    )
    
    coordinator_step.on_function_result(function_name="handle_patient_data").send_event_to(
        target=user_input_step, function_name="get_user_input"
    )
    
    # Handle exit events
    user_input_step.on_event(event_id=MedicalAppointmentEvents.Exit).stop_process()
    user_input_step.on_event(event_id=MedicalAppointmentEvents.ProcessComplete).stop_process()
    
    # Build and start the process
    kernel_process = process.build()
    
    print("🏥 INICIANDO SISTEMA DE CITAS MÉDICAS - CLÍNICAS BUPA")
    print("=" * 60)
    
    await start(
        process=kernel_process,
        kernel=kernel,
        initial_event=KernelProcessEvent(id=MedicalAppointmentEvents.StartProcess, data=None),
    )


if __name__ == "__main__":
    asyncio.run(run_medical_appointment_process())
