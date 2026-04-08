from dataclasses import dataclass

@dataclass
class RecommendationResult:
    condition_category: str  # Good, Average, Bad
    working_status: str     # Working, Not Working
    recommendation: str     # Specific recommendation
    details: str

class RecommendationEngine:
    """
    A lightweight, rule-based recommendation model.
    Maps VLM and YOLO outputs into specific condition strings and actionable advice.
    """
    
    def __init__(self):
        # Damage keywords mapping to severity and condition details
        self.severe_damages = {"burns", "missing components"}
        self.moderate_damages = {"cracks", "broken parts", "exposed wires"}
        self.minor_damages = {"scratches", "dents", "wear and tear"}
        
    def evaluate(self, device_type: str, eco_score: int, damage_indicators: list[str], raw_working_status: str) -> RecommendationResult:
        device = device_type.lower()
        
        # Determine specific details based on indicators or generic if none
        details_str = ", ".join([d.title() for d in damage_indicators])
        if not details_str:
            details_str = "No visible damage detected"
            
        # Determine severity of damages
        has_severe = any(d for d in damage_indicators if d.lower() in self.severe_damages)
        has_moderate = any(d for d in damage_indicators if d.lower() in self.moderate_damages)
        
        # Evaluate Working / Not Working based on VLM raw status or damages
        working_status = "Not Working" if raw_working_status == "damaged" else "Working"
        
        # Inferred "Bad" if severe damages or Not Working with moderate damages
        # Inferred "Average" if working with moderate damages, or working low eco score
        # Inferred "Good" if working and no/minor damages and good eco score
        
        condition_category = "Good"
        if has_severe or (working_status == "Not Working" and has_moderate) or (working_status == "Not Working" and eco_score < 40):
            condition_category = "Bad"
        elif has_moderate or working_status == "Not Working" or eco_score < 75:
            condition_category = "Average"
            
        # Hard cap condition based on raw working status constraints
        if working_status == "Not Working" and condition_category == "Good":
            condition_category = "Average"
            
        # Generate specific recommendation matrix
        recommendation = self._generate_recommendation(device, condition_category, working_status, eco_score, damage_indicators)
            
        return RecommendationResult(
            condition_category=condition_category,
            working_status=working_status,
            recommendation=recommendation,
            details=details_str
        )
        
    def _generate_recommendation(self, device: str, condition: str, status: str, eco: int, damages: list[str]) -> str:
        # High value device heuristics (Mobile, Laptop)
        is_high_value = "laptop" in device or "mobile" in device or "phone" in device or "iphone" in device or "tablet" in device or "macbook" in device
        
        has_battery = "battery" in device or is_high_value
        is_pcb = "pcb" in device or "board" in device
        has_screen_damage = any(d for d in damages if d in ["cracks", "broken parts"])
        
        if condition == "Good" and status == "Working":
            if is_high_value:
                return "Device is in great condition. Recommended for direct resale or premium refurbishing to maximize profit."
            else:
                return "Component/Device is fully functional. Good candidate for secondary markets or reuse."
                
        if condition == "Average" and status == "Working":
            if is_high_value:
                if has_screen_damage:
                    return "Device fundamentally works but has visible damage. Recommended for screen/housing repair followed by resale."
                return "Device shows wear but is functional. Grade B refurbishing recommended."
            return "Functional but worn. Send to secondary market or entry-level refurbishing."
            
        if condition == "Average" and status == "Not Working":
            if is_high_value:
                return "Device not functional but holds value. Recommended for diagnostic repair, or harvest high-value components (CPU, Memory, Camera)."
            if is_pcb:
                return "Non-functional PCB. Recommended for micro-soldering repair or extracting valuable IC chips."
            return "Non-functional item. Repair is viable only if parts are cheap, otherwise process for valuable materials extraction."
            
        if condition == "Bad":
            recommendation = "Device is severely damaged or dead. Recommended for raw material recycling (E-waste processor). "
            if has_battery and "burns" not in damages:
                recommendation += "Caution: Extract battery safely before shredding. "
            if eco > 60:
                recommendation += "Despite condition, standard material recovery should yield good results."
            else:
                recommendation += "Material value is low, treat as low-grade e-scrap."
            return recommendation
            
        return "Standard diagnostic process recommended."
