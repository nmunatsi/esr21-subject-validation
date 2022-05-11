import re
from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from edc_base.utils import age
from edc_constants.constants import MALE, FEMALE, YES
from edc_form_validators import FormValidator


class InformedConsentFormValidator(FormValidator):
    eligibility_confirmation_model = 'esr21_subject.eligibilityconfirmation'
    consent_model = 'esr21_subject.informedconsent'

    @property
    def eligibility_confirmation_cls(self):
        return django_apps.get_model(self.eligibility_confirmation_model)

    @property
    def informed_consent_cls(self):
        return django_apps.get_model(self.consent_model)

    def clean(self):
        self.screening_identifier = self.cleaned_data.get('screening_identifier')
        super().clean()

        self.validate_gender_other()
        self.validate_reconsent()
        self.validate_dob()
        self.validate_identity_number(cleaned_data=self.cleaned_data)

    def validate_gender_other(self):
        self.validate_other_specify(field='gender')

    def validate_identity_number(self, cleaned_data=None):
        identity = cleaned_data.get('identity')
        if identity:
            id_regex = r'[A-Z0-9]+'
            if not re.match(id_regex, identity):
                message = {'identity': 'Identity number must be digits.'}
                self._errors.update(message)
                raise ValidationError(message)
            if cleaned_data.get('identity') != cleaned_data.get(
                    'confirm_identity'):
                msg = {'identity':
                           '\'Identity\' must match \'confirm identity\'.'}
                self._errors.update(msg)
                raise ValidationError(msg)
            if cleaned_data.get('identity_type') == 'national_identity_card':
                if len(cleaned_data.get('identity')) != 9:
                    msg = {'identity':
                               'National identity provided should contain 9 values.'
                               ' Please correct.'}
                    self._errors.update(msg)
                    raise ValidationError(msg)
                gender = cleaned_data.get('gender')
                if gender == FEMALE and cleaned_data.get('identity')[4] != '2':
                    msg = {'identity':
                               'Participant gender is Female. Please correct '
                               'identity number.'}
                    self._errors.update(msg)
                    raise ValidationError(msg)
                elif gender == MALE and cleaned_data.get('identity')[4] != '1':
                    msg = {'identity':
                               'Participant is Male. Please correct identity '
                               'number.'}
                    self._errors.update(msg)
                    raise ValidationError(msg)

    def validate_dob(self):
        dob = self.cleaned_data.get('dob')
        try:
            consent_obj = self.informed_consent_cls.objects.get(
                subject_identifier=self.cleaned_data.get('subject_identifier'),
                version='1')
        except self.informed_consent_cls.DoesNotExist:
            try:
                eligibility_confirmation = self.eligibility_confirmation_cls.objects.get(
                    screening_identifier=self.screening_identifier)
            except self.eligibility_confirmation_cls.DoesNotExist:
                raise ValidationError('Please complete the Eligibility Confirmation '
                                      'form first.')
            else:

                consent_date = self.cleaned_data.get('consent_datetime').date()
                age_in_years = age_in_years = age(dob, consent_date).years

                if (eligibility_confirmation.age_in_years
                        and eligibility_confirmation.age_in_years != age_in_years):
                    message = {'dob':
                                   'The age derived from Date of birth does not '
                                   'match the age provided in the Eligibility Confirmation'
                                   f' form. Expected \'{eligibility_confirmation.age_in_years}\' '
                                   f'got \'{age_in_years}\''}
                    self._errors.update(message)
                    raise ValidationError(message)
        else:
            if consent_obj.dob != dob:
                message = {'dob': 'The dob does not match with the dob of previous consent, '
                           f'Got {dob} but previous consent dob is {consent_obj.dob}'
                           }
                self._errors.update(message)
                raise ValidationError(message)

    def validate_reconsent(self):
        try:
            consent_obj = self.informed_consent_cls.objects.get(
                subject_identifier=self.cleaned_data.get('subject_identifier'),
                version=self.cleaned_data.get('version'))
        except self.informed_consent_cls.DoesNotExist:
            pass
        else:
            consent_dict = consent_obj.__dict__
            consent_fields = [
                'first_name', 'last_name', 'dob', 'recruit_source',
                'recruit_source_other', 'recruitment_clinic',
                'recruitment_clinic_other', 'is_literate', 'identity',
                'identity_type']
            for field in consent_fields:
                if self.cleaned_data.get(field) != consent_dict[field]:
                    message = {field:
                               f'{field} was previously reported as, '
                               f'{consent_dict[field]}, please correct.'}
                    self._errors.update(message)
                    raise ValidationError(message)
