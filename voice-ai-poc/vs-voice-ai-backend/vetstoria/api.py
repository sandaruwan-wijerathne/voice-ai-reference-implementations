from typing import List

import requests

from vetstoria.settings import APISettings


class API:
    def __init__(self):
        """
        Initialize the API client with the base URL, partner key, and site hash.
        """
        self.api_settings: APISettings = APISettings()
        self.auth_token = None  # Will store the authentication token

    def authenticate(self):

        """
        Authenticate with the external system and store the auth token.
        """
        url = f"{self.api_settings.auth_url}/partners/{self.api_settings.partner_key}/authentications"
        payload = {"secret": self.api_settings.secret}

        headers = {
            "Site-Hash": self.api_settings.site_hash,
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/96.0.4664.110 Safari/537.36"
            )
        }

        response = requests.post(url=url, headers=headers, json=payload)

        if response.status_code == 200:
            self.auth_token = response.json().get("token")
            return self.auth_token
        else:
            print(response)
            response.raise_for_status()

    def _get_headers(self):
        """
        Generate headers for authenticated requests.
        """
        if not self.auth_token:
            print("Authentication token is missing. Call authenticate() first.")
            self.authenticate()
        return {"Authorization": f"Bearer {self.auth_token}", "Content-Type": "application/json", "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/96.0.4664.110 Safari/537.36"
        )}

    def get_species(self):
        """
        Retrieve available species for a given site.
        """
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

        return [species["name"] for species in species_list]
        # url = f"{self.api_settings.base_url}/partners/{self.api_settings.partner_key}/clinics/{self.api_settings.site_hash}/locations/{self.api_settings.site_id}/species"
        # response = requests.get(url, headers=self._get_headers())
        # if response.status_code == 200:
        #     species_list: List = response.json()
        #     return [species["name"] for species in species_list]
        # response.raise_for_status()

    def get_appointment_types(self):
        """
        Retrieve available appointment types for a given site.
        """

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
        return [appointment_type["name"] for appointment_type in appointment_type_list]

        # url = f"{self.api_settings.base_url}/partners/{self.api_settings.partner_key}/clinics/{self.api_settings.site_hash}/locations/{self.api_settings.site_id}/appointmentTypes"
        # response = requests.get(url, headers=self._get_headers())
        # if response.status_code == 200:
        #     appointment_type_list: List = response.json()
        #     return [appointment_type["name"] for appointment_type in appointment_type_list]
        # response.raise_for_status()

    def get_schedules(self):
        """
        Retrieve available schedules for a given site.
        """

        schedule_list: List = [
            {
                "id": 85267,
                "name": "Dr Amy Roberts",
                "displayOrder": 4
            },
            {
                "id": 85268,
                "name": "Dr Michael Norman",
                "displayOrder": 1
            }
        ]
        return [schedule["name"] for schedule in schedule_list]
        # url = f"{self.api_settings.base_url}/partners/{self.api_settings.partner_key}/clinics/{self.api_settings.site_hash}/locations/{self.api_settings.site_id}/schedules"
        # response = requests.get(url, headers=self._get_headers())
        # if response.status_code == 200:
        #     schedule_list: List = response.json()
        #     return [schedule["name"] for schedule in schedule_list]
        # response.raise_for_status()

    def get_slots(self, selected_schedule_id, slot_start, slot_end, selected_appt_type_id, selected_species_id):
        """
        Retrieve available slots based on schedule, time period, appointment type, and species.
        """
        url = f"{self.api_settings.base_url}/partners/{self.api_settings.partner_key}/clinics/{self.api_settings.site_hash}/locations/{self.api_settings.site_id}/slots"
        payload = {
            "scheduleIds": [selected_schedule_id],
            "period": {
                "from": slot_start,
                "to": slot_end
            },
            "appointments": [
                {
                    "index": 1,
                    "appointmentTypeId": selected_appt_type_id,
                    "speciesId": selected_species_id
                }
            ]
        }
        # print(payload)
        response = requests.post(url, json=payload, headers=self._get_headers())
        return response.json() if response.status_code == 200 else response.raise_for_status()

    def place_appointment(self, selected_schedule_id, selected_slot_time, client_first_name, client_last_name,
                          selected_appointment_type_id, selected_species_id,
                          patient_name, notes):
        """
        Place a booking with client and appointment details.
        """
        url = f"{self.api_settings.base_url}/partners/{self.api_settings.partner_key}/clinics/{self.api_settings.site_hash}/bookings/{self.api_settings.booking_hash}"
        payload = {
            "locationId": int(self.api_settings.site_id),
            "slot": {
                "scheduleId": selected_schedule_id,
                "partitionId": 1,
                "dateTime": selected_slot_time
            },
            "client": {
                "id": None,
                "isNewClient": True,
                "firstName": client_first_name,
                "lastName": client_last_name,
                "email": "damjee@petvisor.com",
                "phone": "441234567890",
                "postCode": None
            },
            "appointments": [
                {
                    "index": 1,
                    "appointmentTypeId": selected_appointment_type_id,
                    "speciesId": selected_species_id,
                    "patientId": None,
                    "patientName": patient_name,
                    "notes": notes,
                    "screeningOverrides": []
                }
            ],
            "isPreferredClinician": False
        }
        print(payload)
        response = requests.post(url, json=payload, headers=self._get_headers())
        #response_json = response.json() if response.status_code == 201 else response.raise_for_status()
        if response.status_code == 201:
            response_json = response.json()
        else:
            print(response)
            response.raise_for_status()
        # print(response_json)
        return response_json
