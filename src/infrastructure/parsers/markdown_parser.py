import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from application.agents.data_architect.dda_parser import DDAParser
from domain.dda_models import DDADocument, DataEntity, Relationship, DataQualityRequirement, AccessPattern, Governance


class MarkdownDDAParser(DDAParser):
    """Parser for DDA documents in Markdown format."""
    
    def __init__(self):
        self.supported_extensions = ['.md', '.markdown']
    
    async def parse(self, file_path: str) -> DDADocument:
        """Parse a Markdown DDA document and return structured data."""
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Extract document information
        domain = self._extract_domain(content)
        stakeholders = self._extract_stakeholders(content)
        data_owner = self._extract_data_owner(content)
        effective_date = self._extract_effective_date(content)
        business_context = self._extract_business_context(content)
        
        # Extract entities and relationships
        entities = self._extract_entities(content)
        relationships = self._extract_relationships(content)
        
        # Extract other sections
        data_quality = self._extract_data_quality_requirements(content)
        access_patterns = self._extract_access_patterns(content)
        governance = self._extract_governance(content)
        
        return DDADocument(
            domain=domain,
            stakeholders=stakeholders,
            data_owner=data_owner,
            effective_date=effective_date,
            business_context=business_context,
            entities=entities,
            relationships=relationships,
            data_quality_requirements=data_quality,
            access_patterns=access_patterns,
            governance=governance
        )
    
    def supports_format(self, file_path: str) -> bool:
        """Check if this parser supports the given file format."""
        _, ext = os.path.splitext(file_path.lower())
        return ext in self.supported_extensions
    
    def get_supported_formats(self) -> List[str]:
        """Return list of supported file formats."""
        return self.supported_extensions
    
    def _extract_domain(self, content: str) -> str:
        """Extract domain from document information section."""
        # Try multiple patterns
        patterns = [
            r'\*\*Domain\*\*:\s*(.+)',
            r'Domain:\s*(.+)',
            r'# Domain:\s*(.+)',
            r'#\s*Domain\s*\n(.+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
                
        raise ValueError("Domain not found in DDA document")
    
    def _extract_stakeholders(self, content: str) -> List[str]:
        """Extract stakeholders from document information section."""
        pattern = r'\*\*Stakeholders\*\*:\s*(.+)'
        match = re.search(pattern, content)
        if match:
            stakeholders_str = match.group(1).strip()
            # Split by comma and clean up
            return [s.strip() for s in stakeholders_str.split(',')]
        return []
    
    def _extract_data_owner(self, content: str) -> str:
        """Extract data owner from document information section."""
        pattern = r'\*\*Data Owner\*\*:\s*(.+)'
        match = re.search(pattern, content)
        if match:
            return match.group(1).strip()
        return "Unknown"
    
    def _extract_effective_date(self, content: str) -> datetime:
        """Extract effective date from document information section."""
        pattern = r'\*\*Effective Date\*\*:\s*(\d{4}-\d{2}-\d{2})'
        match = re.search(pattern, content)
        if match:
            date_str = match.group(1)
            return datetime.fromisoformat(date_str)
        return datetime.now()
    
    def _extract_business_context(self, content: str) -> str:
        """Extract business context section."""
        # Look for the Business Context section
        pattern = r'## Business Context\s*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return "No business context provided"
    
    def _extract_entities(self, content: str) -> List[DataEntity]:
        """Extract data entities from the document."""
        entities = []
        
        # Find the Data Entities section
        pattern = r'## Data Entities\s*\n(.*?)(?=\n## Relationships|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            print("DEBUG: No 'Data Entities' section found")
            return entities
        
        entities_section = match.group(1)
        print(f"DEBUG: Entities section length: {len(entities_section)}")
        
        # Split by entity headers (### Entity Name)
        # First, remove the leading ### from the first entity
        if entities_section.startswith('### '):
            entities_section = entities_section[4:]  # Remove "### "
        
        # Split by entity headers
        entity_blocks = re.split(r'\n### ', entities_section)
        
        for block in entity_blocks:  # Process all blocks
            entity = self._parse_entity_block(block)
            if entity:
                entities.append(entity)
        
        return entities
    
    def _parse_entity_block(self, block: str) -> Optional[DataEntity]:
        """Parse a single entity block."""
        lines = block.strip().split('\n')
        if not lines:
            return None
        
        # Extract entity name from first line
        name = lines[0].strip()
        
        # Extract description
        description = ""
        attributes = []
        business_rules = []
        primary_key = None
        foreign_keys = []
        
        in_attributes = False
        in_business_rules = False
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('- **Description**:'):
                description = line.replace('- **Description**:', '').strip()
            elif line.startswith('- **Key Attributes**:'):
                in_attributes = True
                in_business_rules = False
            elif line.startswith('- **Business Rules**:'):
                in_attributes = False
                in_business_rules = True
            elif in_attributes and line.startswith('- '):
                attr = line.replace('- ', '').strip()
                if attr:
                    attributes.append(attr)
            elif in_business_rules and line.startswith('- '):
                rule = line.replace('- ', '').strip()
                if rule:
                    business_rules.append(rule)
            elif in_attributes or in_business_rules:
                # Continue collecting attributes or rules
                if line.startswith('- '):
                    item = line.replace('- ', '').strip()
                    if in_attributes:
                        attributes.append(item)
                    else:
                        business_rules.append(item)
        
        # Extract primary key from attributes
        for attr in attributes:
            if '(Primary Key)' in attr:
                primary_key = attr.split('(')[0].strip()
                break
        
        # Extract foreign keys from attributes
        for attr in attributes:
            if '(Foreign Key)' in attr:
                foreign_key = attr.split('(')[0].strip()
                foreign_keys.append(foreign_key)
        
        return DataEntity(
            name=name,
            description=description,
            attributes=attributes,
            business_rules=business_rules,
            primary_key=primary_key,
            foreign_keys=foreign_keys
        )
    
    def _extract_relationships(self, content: str) -> List[Relationship]:
        """Extract relationships from the document."""
        relationships = []
        
        # Find the Relationships section
        pattern = r'## Relationships\s*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return relationships
        
        relationships_section = match.group(1)
        
        # Look for relationship patterns directly in the entire section
        relationship_pattern = r'\*\*([^*]+)\*\*\s*→\s*\*\*([^*]+)\*\*\s*\(([^)]+)\)'
        matches = re.findall(relationship_pattern, relationships_section)
        
        for source_entity, target_entity, relationship_type in matches:
            # Find the description for this relationship
            description = ""
            lines = relationships_section.split('\n')
            for i, line in enumerate(lines):
                if f"**{source_entity}** → **{target_entity}**" in line:
                    # Look for description in next lines
                    for j in range(i + 1, min(i + 5, len(lines))):
                        if lines[j].strip().startswith('- ') and not lines[j].strip().startswith('- **'):
                            description = lines[j].strip()[2:]  # Remove "- "
                            break
                    break
            
            relationship = Relationship(
                source_entity=source_entity.strip(),
                target_entity=target_entity.strip(),
                relationship_type=relationship_type.strip(),
                description=description,
                constraints=[]
            )
            relationships.append(relationship)
        
        return relationships
    
    def _parse_relationship_block(self, block: str) -> Optional[Relationship]:
        """Parse a single relationship block."""
        lines = block.strip().split('\n')
        if not lines:
            return None
        
        # Extract relationship name from first line
        relationship_name = lines[0].strip()
        
        source_entity = ""
        target_entity = ""
        relationship_type = ""
        description = ""
        constraints = []
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('- **'):
                # Parse relationship details
                if '→' in line:
                    # Extract entities and relationship type
                    parts = line.split('→')
                    if len(parts) == 2:
                        source_part = parts[0].strip()
                        target_part = parts[1].strip()
                        
                        # Extract source entity
                        source_match = re.search(r'\*\*(.+?)\*\*', source_part)
                        if source_match:
                            source_entity = source_match.group(1)
                        
                        # Extract target entity and relationship type
                        target_match = re.search(r'\*\*(.+?)\*\*', target_part)
                        if target_match:
                            target_entity = target_match.group(1)
                        
                        # Extract relationship type
                        type_match = re.search(r'\(([^)]+)\)', target_part)
                        if type_match:
                            relationship_type = type_match.group(1)
            
            elif line.startswith('- '):
                # This is likely a description or constraint
                item = line.replace('- ', '').strip()
                if not description:
                    description = item
                else:
                    constraints.append(item)
        
        return Relationship(
            source_entity=source_entity,
            target_entity=target_entity,
            relationship_type=relationship_type,
            description=description,
            constraints=constraints
        )
    
    def _extract_data_quality_requirements(self, content: str) -> DataQualityRequirement:
        """Extract data quality requirements."""
        # This is a simplified extraction - in a real implementation,
        # you'd want more sophisticated parsing
        return DataQualityRequirement()
    
    def _extract_access_patterns(self, content: str) -> AccessPattern:
        """Extract access patterns."""
        # This is a simplified extraction - in a real implementation,
        # you'd want more sophisticated parsing
        return AccessPattern()
    
    def _extract_governance(self, content: str) -> Governance:
        """Extract governance requirements."""
        # This is a simplified extraction - in a real implementation,
        # you'd want more sophisticated parsing
        return Governance()


# Add missing import
import os 