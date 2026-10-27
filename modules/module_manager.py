#!/usr/bin/env python3
"""
Dynamic module system: trigger evaluation and module group management.

Extracted unchanged from upstream main_daemon.py (eink_weather_2) so that the
web edition does not depend on the Raspberry Pi daemon or Waveshare drivers.
"""

import re
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any


class TriggerEvaluator:
    """
    Säker evaluering av trigger-conditions för Dynamic Module System

    Stöder conditions som: "precipitation > 0 OR forecast_precipitation_2h > 0.2"
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.TriggerEvaluator")

        # Whitelisted functions för säker evaluation
        self.safe_functions = {
            'precipitation': self._get_precipitation,
            'forecast_precipitation_2h': self._get_forecast_precipitation_2h,
            'temperature': self._get_temperature,
            'wind_speed': self._get_wind_speed,
            'pressure_trend': self._get_pressure_trend,
            'time_hour': self._get_current_hour,
            'time_month': self._get_current_month,
            'user_preference': self._get_user_preference,
            'is_daylight': self._get_is_daylight,
            'pcat': self._get_pcat,
        }

    def evaluate_condition(self, condition: str, context: Dict) -> bool:
        """
        Säkert evaluera trigger-condition med whitelisted functions

        Args:
            condition: Condition string (t.ex. "precipitation > 0 OR temperature < 5")
            context: Context data för evaluation

        Returns:
            True om condition är uppfylld, False annars
        """
        try:
            if not condition or not isinstance(condition, str):
                return False

            # Ersätt function calls med värden
            evaluated_condition = self._replace_functions_with_values(condition, context)

            # Säker evaluation av logisk expression
            result = self._safe_eval_logic(evaluated_condition)

            self.logger.debug(f"🎯 Trigger condition: '{condition}' → '{evaluated_condition}' → {result}")
            return result

        except Exception as e:
            self.logger.error(f"❌ Fel vid trigger evaluation: {condition} - {e}")
            return False

    def _replace_functions_with_values(self, condition: str, context: Dict) -> str:
        """Ersätt function calls med faktiska värden"""
        import re
        result = condition

        # Sortera functions efter längd (längsta först) för att undvika partiella ersättningar
        sorted_functions = sorted(self.safe_functions.items(), key=lambda x: len(x[0]), reverse=True)

        for func_name, func in sorted_functions:
            # Använd word boundaries för exakt matchning
            pattern = r'\b' + re.escape(func_name) + r'\b'
            if re.search(pattern, result):
                try:
                    value = func(context)
                    # Ersätt HELA function name med värdet
                    result = re.sub(pattern, str(value), result)
                    self.logger.debug(f"🔄 Replaced {func_name} → {value}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Function {func_name} fel: {e}")
                    result = re.sub(pattern, "0", result)  # Fallback

        return result

    def _safe_eval_logic(self, expression: str) -> bool:
        """
        Säker evaluation av logisk expression
        Endast tillåter: numbers, operators (>, <, >=, <=, ==, !=), AND, OR, NOT, ()
        """
        try:
            # Whitelist för tillåtna tokens
            allowed_chars = set('0123456789.<>=!() ')
            allowed_words = {'AND', 'OR', 'NOT', 'True', 'False'}

            # Ersätt logiska operatorer med Python syntax.
            # Ordgränser (\b) krävs: kravet på omgivande mellanslag gjorde att
            # uttryck som BÖRJAR med "NOT ..." aldrig konverterades → eval-syntaxfel → alltid False
            expression = re.sub(r'\bAND\b', 'and', expression)
            expression = re.sub(r'\bOR\b', 'or', expression)
            expression = re.sub(r'\bNOT\b', 'not', expression)

            # Kontrollera att endast säkra tokens används
            tokens = expression.split()
            for token in tokens:
                if not (all(c in allowed_chars for c in token) or token in allowed_words or token in ['and', 'or', 'not']):
                    self.logger.warning(f"⚠️ Osäker token i expression: {token}")
                    return False

            # Evaluera expression
            result = eval(expression)
            return bool(result)

        except Exception as e:
            self.logger.error(f"❌ Fel vid logic evaluation: {expression} - {e}")
            return False

    # Whitelisted functions för context data
    def _get_precipitation(self, context: Dict) -> float:
        """Hämta aktuell nederbörd från context"""
        return float(context.get('precipitation', 0.0))

    def _get_forecast_precipitation_2h(self, context: Dict) -> float:
        """Hämta prognostiserad nederbörd kommande 2h"""
        return float(context.get('forecast_precipitation_2h', 0.0))

    def _get_temperature(self, context: Dict) -> float:
        """Hämta temperatur från context"""
        return float(context.get('temperature', 20.0))

    def _get_wind_speed(self, context: Dict) -> float:
        """Hämta vindstyrka från context"""
        return float(context.get('wind_speed', 0.0))

    def _get_pressure_trend(self, context: Dict) -> str:
        """Hämta trycktrend från context"""
        return str(context.get('pressure_trend_arrow', 'stable'))

    def _get_current_hour(self, context: Dict) -> int:
        """Hämta aktuell timme"""
        return datetime.now().hour

    def _get_current_month(self, context: Dict) -> int:
        """Hämta aktuell månad"""
        return datetime.now().month

    def _get_user_preference(self, context: Dict) -> str:
        """Hämta användarpreferens från context"""
        return str(context.get('user_preferences', {}).get('module_preference', 'normal'))

    def _get_is_daylight(self, context: Dict) -> bool:
        """Kontrollera om det är dagsljus"""
        return bool(context.get('is_daylight', True))

    def _get_pcat(self, context: Dict) -> int:
        """Hämta precipitation category (pcat) kod från context"""
        return int(context.get('pcat', 0))


class DynamicModuleManager:
    """
    Hanterar dynamiska moduler baserat på triggers och module groups

    Kärnkomponent i Dynamic Module System för villkorsbaserade layout-ändringar
    """

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.DynamicModuleManager")

        # Läs ny config-struktur med fallback till legacy
        self.module_groups = config.get('module_groups', {})
        self.triggers = config.get('triggers', {})
        self.legacy_modules = config.get('modules', {})

        # Trigger evaluator för condition evaluation
        self.trigger_evaluator = TriggerEvaluator()

        # State tracking för layout-ändringar
        self.current_active_groups = {}
        self.last_trigger_evaluation = 0

        self.logger.info(f"🔄 DynamicModuleManager initierad")
        self.logger.info(f"   📊 Module groups: {len(self.module_groups)}")
        self.logger.info(f"   🎯 Triggers: {len(self.triggers)}")

        # Log loaded triggers för debugging (skippa kommentarer)
        for trigger_name, trigger_config in self.triggers.items():
            # Skippa kommentarer som börjar med "_"
            if trigger_name.startswith('_') or not isinstance(trigger_config, dict):
                continue
            condition = trigger_config.get('condition', 'N/A')
            self.logger.info(f"   🎯 {trigger_name}: '{condition}'")

    def evaluate_triggers(self, context_data: Dict) -> Dict[str, str]:
        """
        Evaluera alla triggers och returnera aktiva module groups

        Args:
            context_data: Väderdata, användarpref, tid, etc.

        Returns:
            Dict med section → active group mapping
            Exempel: {"bottom_section": "precipitation_active", "side_panel": "normal"}
        """
        try:
            active_groups = {}

            # Börja med default groups (normal för alla sections)
            for section_name, groups in self.module_groups.items():
                if 'normal' in groups:
                    active_groups[section_name] = 'normal'
                else:
                    # Använd första tillgängliga group som default
                    first_group = list(groups.keys())[0] if groups else None
                    if first_group:
                        active_groups[section_name] = first_group

            # Evaluera triggers med priority-ordning (skippa kommentarer)
            triggers_by_priority = sorted(
                [(name, config) for name, config in self.triggers.items()
                 if not name.startswith('_') and isinstance(config, dict)],
                key=lambda x: x[1].get('priority', 50),
                reverse=True  # Högsta priority först
            )

            # Sektioner som redan avgjorts av en aktiv trigger med högre prioritet.
            # Utan denna spärr skrev VARJE efterföljande aktiv trigger över sektionen,
            # så lägst prioritet vann - tvärtemot avsedd semantik.
            claimed_sections = set()

            for trigger_name, trigger_config in triggers_by_priority:
                try:
                    condition = trigger_config.get('condition', '')
                    target_section = trigger_config.get('target_section', '')
                    activate_group = trigger_config.get('activate_group', '')

                    if not all([condition, target_section, activate_group]):
                        self.logger.warning(f"⚠️ Ofullständig trigger config: {trigger_name}")
                        continue

                    if target_section in claimed_sections:
                        self.logger.debug(f"🎯 Trigger {trigger_name} skippad: {target_section} redan avgjord av högre prioritet")
                        continue

                    # Evaluera condition
                    if self.trigger_evaluator.evaluate_condition(condition, context_data):
                        # Trigger är aktiv → aktivera group
                        active_groups[target_section] = activate_group
                        claimed_sections.add(target_section)
                        self.logger.info(f"🎯 Trigger aktiverad: {trigger_name} → {target_section}.{activate_group}")
                    else:
                        self.logger.debug(f"🎯 Trigger inaktiv: {trigger_name}")

                except Exception as e:
                    self.logger.error(f"❌ Fel vid trigger evaluation: {trigger_name} - {e}")
                    continue

            self.current_active_groups = active_groups
            self.last_trigger_evaluation = time.time()

            return active_groups

        except Exception as e:
            self.logger.error(f"❌ Fel vid trigger evaluation: {e}")
            # Fallback: alla sections till normal
            return {section: 'normal' for section in self.module_groups.keys()}

    def get_active_modules(self, context_data: Dict) -> List[str]:
        """
        Returnera lista av moduler som ska renderas baserat på aktiva groups

        Args:
            context_data: Context data för trigger evaluation

        Returns:
            Lista av modulnamn som ska renderas
        """
        try:
            # Evaluera triggers för att få aktiva groups
            active_groups = self.evaluate_triggers(context_data)

            active_modules = []

            # Samla moduler från aktiva groups
            for section_name, active_group in active_groups.items():
                if section_name in self.module_groups:
                    section_groups = self.module_groups[section_name]
                    if active_group in section_groups:
                        group_modules = section_groups[active_group]
                        active_modules.extend(group_modules)
                        self.logger.debug(f"📊 Section {section_name}: {active_group} → {group_modules}")

            # Fallback: använd legacy modules om inga groups är definierade
            if not active_modules and self.legacy_modules:
                active_modules = [name for name, config in self.legacy_modules.items() if isinstance(config, dict) and config.get('enabled', False)]
                self.logger.info("🔄 Använder legacy modules (inga groups definierade)")

            self.logger.info(f"🎯 Aktiva moduler: {active_modules}")
            return active_modules

        except Exception as e:
            self.logger.error(f"❌ Fel vid hämtning av aktiva moduler: {e}")
            # Fallback: legacy modules
            return [name for name, config in self.legacy_modules.items() if config.get('enabled', False)]

    def get_current_layout_state(self, context_data: Dict) -> Dict[str, Any]:
        """
        Få aktuellt layout-state för change detection

        Args:
            context_data: Context data för trigger evaluation

        Returns:
            Dict med layout state information
        """
        active_groups = self.evaluate_triggers(context_data)
        active_modules = self.get_active_modules(context_data)

        return {
            'active_groups': active_groups,
            'active_modules': active_modules,
            'trigger_evaluation_time': self.last_trigger_evaluation
        }

    def should_layout_update(self, context_data: Dict, last_layout_state: Dict) -> tuple:
        """
        Kontrollera om layout har ändrats sedan senast

        Args:
            context_data: Aktuell context data
            last_layout_state: Tidigare layout state

        Returns:
            Tuple (should_update: bool, reason: str)
        """
        try:
            current_layout_state = self.get_current_layout_state(context_data)

            if not last_layout_state:
                return True, "Första layout evaluation"

            # Jämför aktiva groups
            last_groups = last_layout_state.get('active_groups', {})
            current_groups = current_layout_state.get('active_groups', {})

            if last_groups != current_groups:
                changes = []
                for section in set(list(last_groups.keys()) + list(current_groups.keys())):
                    last_group = last_groups.get(section, 'none')
                    current_group = current_groups.get(section, 'none')
                    if last_group != current_group:
                        changes.append(f"{section}: {last_group}→{current_group}")

                return True, f"Layout-ändring: {', '.join(changes)}"

            # Jämför aktiva moduler
            last_modules = set(last_layout_state.get('active_modules', []))
            current_modules = set(current_layout_state.get('active_modules', []))

            if last_modules != current_modules:
                added = current_modules - last_modules
                removed = last_modules - current_modules
                changes = []
                if added:
                    changes.append(f"Tillagda: {', '.join(added)}")
                if removed:
                    changes.append(f"Borttagna: {', '.join(removed)}")

                return True, f"Modul-ändring: {'; '.join(changes)}"

            return False, "Ingen layout-ändring"

        except Exception as e:
            self.logger.error(f"❌ Fel vid layout change detection: {e}")
            return True, f"Fel vid layout-kontroll: {e}"

    def build_trigger_context(self, weather_data: Dict) -> Dict[str, Any]:
        """
        Bygg komplett context för trigger evaluation

        Args:
            weather_data: Väderdata från weather_client

        Returns:
            Dict med all context data för triggers
        """
        try:
            now = datetime.now()

            # Extrahera cykel-väder data om tillgängligt
            cycling_weather = weather_data.get('cycling_weather', {})

            context = {
                # Väderdata
                'precipitation': weather_data.get('precipitation', 0.0),
                'forecast_precipitation_2h': cycling_weather.get('precipitation_mm', 0.0),  # Från cykel-väder analys
                'temperature': weather_data.get('temperature', 20.0),
                'wind_speed': weather_data.get('wind_speed', 0.0),
                'pcat': cycling_weather.get('pcat', 0),  # NYTT: rå pcat-kod för snöfiltrering
                'pressure_trend_arrow': weather_data.get('pressure_trend_arrow', 'stable'),

                # Temporal context
                'time_hour': now.hour,
                'time_month': now.month,
                'time_weekday': now.weekday(),
                'is_daylight': self._determine_daylight(weather_data),

                # User context (från config)
                'user_preferences': self.config.get('user_preferences', {}),

                # System context
                'display_mode': self.config.get('display_mode', 'normal'),
                'debug_mode': self.config.get('debug', {}).get('enabled', False)
            }

            self.logger.debug(f"🌐 Trigger context: precipitation={context['precipitation']}, forecast_2h={context['forecast_precipitation_2h']}")
            return context

        except Exception as e:
            self.logger.error(f"❌ Fel vid context building: {e}")
            return {}

    def _determine_daylight(self, weather_data: Dict) -> bool:
        """Bestäm om det är dagsljus baserat på soldata"""
        try:
            sun_data = weather_data.get('sun_data', {})
            sunrise_time = weather_data.get('parsed_sunrise')
            sunset_time = weather_data.get('parsed_sunset')

            if sunrise_time and sunset_time:
                now = datetime.now()
                return sunrise_time <= now <= sunset_time
            else:
                # Fallback: 06:00-18:00 = dagsljus
                hour = datetime.now().hour
                return 6 <= hour <= 18

        except Exception as e:
            self.logger.warning(f"⚠️ Fel vid dagsljus-bestämning: {e}")
            return True  # Default till dagsljus

