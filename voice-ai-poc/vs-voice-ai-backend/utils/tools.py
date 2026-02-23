import asyncio
import json
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import List, Optional

from langchain_core.tools import tool
from starlette.websockets import WebSocket

from vetstoria.api import API

# Context variable to store the current websocket connection
current_websocket: ContextVar[Optional[WebSocket]] = ContextVar('current_websocket', default=None)

# Context variable to track if an appointment was booked in the current conversation
appointment_booked: ContextVar[bool] = ContextVar('appointment_booked', default=False)

# Context variable to store the current conversation ID
current_conversation_id: ContextVar[Optional[int]] = ContextVar('current_conversation_id', default=None)

# Hardcoded to save loading time. Threse need to be pre-loaded and cached based on account hash.
species_list: List = [
    {
        "id": 1,
        "name": "Dog",
        "displayOrder": 1
    },
    {
        "id": 2,
        "name": "Cat",
        "displayOrder": 2
    }
]

# Hardcoded to save loading time. Threse need to be pre-loaded and cached based on account hash.
appointment_type_list: List = [
    {
        "id": 6963,
        "name": "Vaccinations",
        "isDigitalMarketing": False
    },
    {
        "id": 6964,
        "name": "Consultation",
        "isDigitalMarketing": False
    },
    {
        "id": 6966,
        "name": "Nurse appointment",
        "isDigitalMarketing": False
    },
    {
        "id": 6994,
        "name": "Dental",
        "isDigitalMarketing": False
    }
]

# Hardcoded to save loading time. Threse need to be pre-loaded and cached based on account hash.
schedule_list: List = [
    {
        "id": 85267,
        "name": "Dr Amy Roberts",
        "displayOrder": 2
    },
    {
        "id": 85268,
        "name": "Dr Michael Norman",
        "displayOrder": 1
    }
]


@tool
def get_available_time_slots(preferred_date: str, preferred_time_period: str, species: str, clinician: str,
                             appointment_type: str) -> str:
    """
    Get available time slots for a specific date.

    Parameters:
        preferred_date (str): User preferred date. Should be in %Y-%m-%d format.
        preferred_time_period (str): User selected preferred time slot.
            It must be exactly one of these: "MORNING", "AFTERNOON" or "EVENING".
        species (str): User selected species.
            It must be exactly one of these: [Dog, Cat].
        clinician (str): User selected clinician.
            It must be exactly one of these: [Dr Amy Roberts, Dr Michael Norman].
        appointment_type (str): User selected appointment type.
            It must be exactly one of these: [Vaccinations, Consultation, Nurse appointment, Dental].
    Returns:
        str: Available time slots for the given criteria.
    """
    if preferred_time_period == "MORNING":
        from_timestamp = datetime.strptime(preferred_date, "%Y-%m-%d").replace(hour=7, minute=0, second=0,
                                                                               tzinfo=timezone.utc)
        to_timestamp = datetime.strptime(preferred_date, "%Y-%m-%d").replace(hour=12, minute=0, second=0,
                                                                             tzinfo=timezone.utc)
    elif preferred_time_period == "AFTERNOON":
        from_timestamp = datetime.strptime(preferred_date, "%Y-%m-%d").replace(hour=12, minute=0, second=1,
                                                                               tzinfo=timezone.utc)
        to_timestamp = datetime.strptime(preferred_date, "%Y-%m-%d").replace(hour=17, minute=0, second=0,
                                                                             tzinfo=timezone.utc)    
    else:
        from_timestamp = datetime.strptime(preferred_date, "%Y-%m-%d").replace(hour=17, minute=0, second=1,
                                                                               tzinfo=timezone.utc)
        to_timestamp = datetime.strptime(preferred_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59,
                                                                             tzinfo=timezone.utc)
    # Format as string without timezone
    from_str = from_timestamp.isoformat()
    to_str = to_timestamp.isoformat()

    species_id = next((item["id"] for item in species_list if item["name"] == species), None)
    schedule_id = next((item["id"] for item in schedule_list if item["name"] == clinician), None)
    #schedule_id = 85267
    appointment_type_id = next((item["id"] for item in appointment_type_list if item["name"] == appointment_type), None)
    #appointment_type_id = 6963
    time_slots = API().get_slots(schedule_id, from_str, to_str, appointment_type_id, species_id)
    categorized_times = {"MORNING": [], "AFTERNOON": [], "EVENING": []}

    print("Time slots retrieved successfully")
    print(time_slots)
    for item in time_slots:
        dt = datetime.fromisoformat(item['dateTime'])  # Convert to datetime object
        time_str = dt.strftime("%H:%M")  # Extract only the time in HH:MM format

        if dt.hour < 12:
            categorized_times["MORNING"].append(time_str)
        elif dt.hour >= 12 and dt.hour < 17:
            categorized_times["AFTERNOON"].append(time_str)
        else:
            categorized_times["EVENING"].append(time_str)
    print(categorized_times)
    #result = f"""
    #        {categorized_times}
    #        If user select MORNING ask preferred time slots from MORNING time slots only 
    #        If user select AFTERNOON ask preferred time slots from AFTERNOON time slots only 
    #        If user select EVENING ask preferred time slots from EVENING time slots only 
    #        Make sure to tell these time slots in ***%I:%M %p*** format to user
    #        """
    result = json.dumps(categorized_times)
    return result


@tool
def place_appointment(preferred_date: str, preferred_time: str, species: str, clinician: str,
                      appointment_type: str, client_first_name: str, client_last_name: str, pet_name: str,
                      notes: str) -> str | None:

    """
   Places an appointment with relevant details.

   Parameters:
       preferred_date (str): User preferred date. Should be in %Y-%m-%d format.
       preferred_time (str): User selected preferred time. Should be in ***%I:%M %p*** format.
       species (str): User selected species.
        It must be exactly one of these: [Dog, Cat].
       clinician (str): User selected clinician.
        It must be exactly one of these: [Dr Amy Roberts, Dr Michael Norman].
       appointment_type (str): User selected appointment type.
        It must be exactly one of these: [Vaccinations, Consultation, Nurse appointment, Dental].
       client_first_name (str): User's first name.
       client_last_name (str): User's last name.
       pet_name (str): Pet name.
       notes (str): Special notes related to the booking.

   Returns:
       str: Confirmation message or booking reference.
   """
    date_obj = datetime.strptime(preferred_date, "%Y-%m-%d").date()

    time_obj = datetime.strptime(preferred_time, "%I:%M %p").time()

    combined_datetime = datetime.combine(date_obj, time_obj)

    iso_format = combined_datetime.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    species_id = next((item["id"] for item in species_list if item["name"] == species), None)
    schedule_id = next((item["id"] for item in schedule_list if item["name"] == clinician), None)
    appointment_type_id = next((item["id"] for item in appointment_type_list if item["name"] == appointment_type), None)
    appointment = API().place_appointment(schedule_id, iso_format, client_first_name, client_last_name,
                                          appointment_type_id, species_id,
                                          pet_name, notes)
    # print("Placed appointment successfully")
    # print(appointment)
    appointment_id = None
    if isinstance(appointment, dict):
        # Mark that an appointment was successfully booked
        appointment_booked.set(True)
        appointments_list = appointment.get("appointments", [])
        appointment_id = appointments_list[0].get("pimsAppointmentId")
        #if appointments_list:
        #    appointment_id = appointments_list[0].get("pimsAppointmentId")
        #    return f"Your appointment id is: {appointment_id}. Provide this to the user"
        #return "Appointment booked successfully"
        #return {"status": "success", "appointment_id": appointments_list[0].get("pimsAppointmentId")}
    if isinstance(appointment, list):
        appointment_id = appointment[0]
        # Mark that an appointment was successfully booked
        appointment_booked.set(True)
        #return appointment[0]
    
    return {"status": "success", "appointment_id": appointment_id}

@tool
async def close_websocket(reason: str = "User requested to end the conversation") -> str:
    """
    Close the WebSocket connection and end the conversation.
    
    Parameters:
        reason (str): Optional reason for closing the connection. Defaults to "User requested to end the conversation".
    
    Returns:
        str: Confirmation message that the connection will be closed.
    """
    websocket = current_websocket.get()
    if websocket:
        # Schedule the close in the background after 5 seconds
        # This allows the tool to return immediately so the LLM can send final messages
        async def delayed_close():
            await asyncio.sleep(10)
            await websocket.close(code=1000, reason=reason)
        
        asyncio.create_task(delayed_close())
        return {"status": "success"}
    return {"status": "error", "message": "No active connection to close"}


TOOLS_MAP = {
    "place_appointment": place_appointment,
    "get_available_time_slots": get_available_time_slots,
    "close_websocket": close_websocket
}
TOOLS = {
    "place_appointment": place_appointment,
    "get_available_time_slots": get_available_time_slots,
    "close_websocket": close_websocket
}
TOOLS_ARRAY = [place_appointment, get_available_time_slots, close_websocket]