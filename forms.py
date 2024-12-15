from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, IntegerField, SubmitField, FormField, StringField, FieldList, SelectField, DateField
from wtforms.validators import DataRequired, NumberRange, Optional

class BuildInitForm(FlaskForm):
    
    
    
    # Active plans (checkboxes)
    active_plans = SelectMultipleField(
        'Active Plans',
        choices=[],  # Choices will be dynamically populated in the route
        coerce=int,  # Plan IDs will be integers
         # At least one plan must be selected
    )
    

    # New plan numbers for each funding type and coverage
    self_funded_medical = IntegerField('Self-Funded Medical', validators=[NumberRange(min=0)], default=0)
    self_funded_dental = IntegerField('Self-Funded Dental', validators=[NumberRange(min=0)], default=0)
    self_funded_vision = IntegerField('Self-Funded Vision', validators=[NumberRange(min=0)], default=0)

    fully_insured_medical = IntegerField('Fully-Insured Medical', validators=[NumberRange(min=0)], default=0)
    fully_insured_dental = IntegerField('Fully-Insured Dental', validators=[NumberRange(min=0)], default=0)
    fully_insured_vision = IntegerField('Fully Insured Vision', validators=[NumberRange(min=0)], default=0)
    
    level_funded_medical = IntegerField('Level-Funded Medical', validators=[NumberRange(min=0)], default=0)
    level_funded_dental = IntegerField('Level-Funded Dental', validators=[NumberRange(min=0)], default=0)
    level_funded_vision = IntegerField('Level-Funded Vision', validators=[NumberRange(min=0)], default=0)
    
    min_prem_medical = IntegerField('Min-Prem Medical', validators=[NumberRange(min=0)], default=0)
    min_prem_dental = IntegerField('Min-Prem Dental', validators=[NumberRange(min=0)], default=0)
    min_prem_vision = IntegerField('Min-Prem Vision', validators=[NumberRange(min=0)], default=0)

    submit = SubmitField('Proceed')


class TierForm(FlaskForm):
    tier_name = StringField("Tier Name", validators=[Optional()])
    single_family = StringField("Single/Family", validators=[Optional()])

class TierStructureForm(FlaskForm):
    number_of_tiers = SelectField(
        "Number of Tiers",
        choices=[(i, str(i)) for i in range(1, 9)],
        coerce=int,
        default=8,
        validators=[DataRequired()]
    )
    tiers = FieldList(
        FormField(TierForm),
        min_entries=8,
        max_entries=8
    )
    selected_plans = FieldList(
        StringField("Plan", validators=[Optional()]),
        min_entries=1
    )
    submit = SubmitField("Proceed")

class SummaryOptionForm(FlaskForm):
    option = StringField('Summary Option', validators=[Optional()])

class RateStructureForm(FlaskForm):
    rate_name = StringField('Rate Structure Name', validators=[Optional()])
    summary_options = FieldList(FormField(SummaryOptionForm), min_entries=8)
    selected_plans = SelectMultipleField('Plans', validators=[Optional()], coerce=str)

class RateStructuresForm(FlaskForm):
    rate_structures = FieldList(FormField(RateStructureForm), min_entries=1)
    submit = SubmitField("Submit Rates")
