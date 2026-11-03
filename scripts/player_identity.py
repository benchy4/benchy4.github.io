ALIASES={
 "Miela Goodchild":"Miela Sowah",
 "Chantel Anais Horvat":"Chantel-Anais Horvat",
 "Abby Kate Bishop":"Abby Bishop",
 "Chelsea Brooks":"Chelsea Brook",
 "Isabel Borlase":"Isobel Borlase",
 "Kristy Anne Wallace":"Kristy Wallace",
 "Caitlin Martin":"Caitlyn Martin",
 "Xu Han":"Han Xu",
 "Abbey Wehrung":"Abigail Wehrung",
 "Alexandra Sharp":"Alex Sharp",
}

def canonical_player(name):
 return ALIASES.get(name,name)

def player_aliases(name):
 canonical=canonical_player(name)
 return {canonical}|{alias for alias,target in ALIASES.items() if target==canonical}

PLAYER_SUM_FIELDS={
 "games","minutes_seconds","points","fg_made","fg_attempted","three_made","three_attempted",
 "ft_made","ft_attempted","rebounds","offensive_rebounds","defensive_rebounds","assists",
 "steals","turnovers","blocks","fouls","observed_assists","points_created","three_point_assists",
 "made_field_goals","made_field_goal_points","assisted_makes","assisted_points","clutch_assists_x",
 "clutch_events","clutch_points","clutch_fga","clutch_fgm","clutch_turnovers","clutch_steals",
 "clutch_offensive_rebounds","clutch_assists_y",
}
PLAYER_MAX_FIELDS={"scorer_partners","play_types_created","unique_assisters","assisted_play_types"}

def merge_player_season_rows(rows):
 """Collapse source-name aliases into one player-season without double-listing the player."""
 groups={}
 for source in rows:
  row=dict(source);row["player_name"]=canonical_player(row.get("player_name"))
  row["season"]=str(row.get("season"))
  key=(str(row.get("season")),row.get("team"),row.get("player_name"))
  groups.setdefault(key,[]).append(row)
 merged=[]
 for group in groups.values():
  if len(group)==1:
   merged.append(group[0]);continue
  base=dict(max(group,key=lambda r:(r.get("games") or 0,r.get("minutes_seconds") or 0)))
  for field in PLAYER_SUM_FIELDS:
   if any(field in row for row in group):base[field]=sum((row.get(field) or 0) for row in group)
  for field in PLAYER_MAX_FIELDS:
   if any(field in row for row in group):base[field]=max((row.get(field) or 0) for row in group)
  primary=max(group,key=lambda r:r.get("primary_assister_makes") or 0)
  base["primary_assister"]=primary.get("primary_assister")
  if len({r.get("primary_assister") for r in group if r.get("primary_assister")})==1:
   base["primary_assister_makes"]=sum((r.get("primary_assister_makes") or 0) for r in group)
  else:base["primary_assister_makes"]=primary.get("primary_assister_makes") or 0
  minutes=base.get("minutes_seconds") or 0
  for numerator,field in (("points","points_per_40"),("assists","assists_per_40"),("turnovers","turnovers_per_40"),("offensive_rebounds","offensive_rebounds_per_40"),("steals","steals_per_40"),("blocks","blocks_per_40")):
   base[field]=(base.get(numerator) or 0)*2400/minutes if minutes else None
  made=base.get("made_field_goals") or base.get("fg_made") or 0
  made_points=base.get("made_field_goal_points") or 0
  assisted=base.get("assisted_makes") or 0
  base["assisted_make_share"]=assisted/made if made else None
  base["assisted_made_point_share"]=(base.get("assisted_points") or 0)/made_points if made_points else None
  base["primary_assister_share_of_assisted_makes"]=(base.get("primary_assister_makes") or 0)/assisted if assisted else None
  base["top_partner_share"]=(base.get("primary_assister_makes") or 0)/(base.get("observed_assists") or 0) if base.get("observed_assists") else None
  base["clutch_fg_percentage"]=(base.get("clutch_fgm") or 0)/(base.get("clutch_fga") or 0) if base.get("clutch_fga") else None
  weight=sum((r.get("observed_assists") or 0) for r in group)
  base["creation_play_type_entropy"]=sum((r.get("creation_play_type_entropy") or 0)*(r.get("observed_assists") or 0) for r in group)/weight if weight else None
  merged.append(base)
 return merged
