"""Team boundaries for the portal's existing tables."""
from sqlalchemy import event, or_
from sqlalchemy.orm import with_loader_criteria

NETKOM = 'netkom'
OCCIDENT = 'occident'
TEAMS = {NETKOM: 'Netkom', OCCIDENT: 'Occident', 'escuela': 'Escuela', 'surne': 'Surne'}
NEW_TEAMS = ('escuela', 'surne')
SHARED_RECORDS = (
    'module:staff', 'module:vehicle', 'archived:staff', 'archived:vehicle',
    'system:vehicle-log', 'shared:space-reservation',
)


def configure_team_scope(sessions, models, record_model):
    @event.listens_for(sessions, 'do_orm_execute')
    def scope_statement(state):
        team = state.session.info.get('team')
        if not team or state.execution_options.get('shared_resource_lookup'):
            return
        if not (state.is_select or state.is_update or state.is_delete):
            return
        options = [
            with_loader_criteria(model, model.team == team, include_aliases=True)
            for model in models
        ]
        options.append(with_loader_criteria(
            record_model,
            or_(record_model.team == team, record_model.kind.in_(SHARED_RECORDS)),
            include_aliases=True,
        ))
        state.statement = state.statement.options(*options)

    @event.listens_for(sessions, 'before_flush')
    def assign_team(session, context, instances):
        team = session.info.get('team')
        if not team:
            return
        for row in session.new:
            if isinstance(row, (*models, record_model)) and row.team is None:
                row.team = team


def team_record_key(team, key):
    return key if team == NETKOM else f'{team}:{key}'
