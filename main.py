from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime

app = FastAPI()

# MongoDB Connection
client = AsyncIOMotorClient("mongodb://localhost:27017")  # Replace with MongoDB Atlas URI if needed
db = client.InventorySystem

# Helper function to convert BSON ObjectId to string
def item_serializer(item) -> dict:
	return {
		"id": str(item["_id"]),
		"name": item["name"],
		"email": item["email"],
		"item_name": item["item_name"],
		"quantity": item["quantity"],
		"expiry_date": item["expiry_date"],
		"insert_date": item["insert_date"]
	}

# Pydantic models
class Item(BaseModel):
    name: str
    email: str
    item_name: str
    quantity: int
    expiry_date: str

class UpdateItem(BaseModel):
    name: Optional[str]
    email: Optional[str]
    item_name: Optional[str]
    quantity: Optional[int]
    expiry_date: Optional[str]

class ClockInRecord(BaseModel):
    email: str
    location: str

class UpdateClockInRecord(BaseModel):
    email: Optional[str]
    location: Optional[str]

# Items CRUD APIs

@app.post(
    "/items", 
    response_model=dict
)
async def create_item(
    item: Item
):
    item_data = item.dict()
    item_data["insert_date"] = datetime.utcnow()
    item_data["expiry_date"] = datetime.strptime(item.expiry_date, '%Y-%m-%d')

    result = await db.items.insert_one(item_data)
    new_item = await db.items.find_one({"_id": result.inserted_id})

    return item_serializer(new_item)

@app.get(
    "/items/filter", 
    response_model=List[dict]
)
async def filter_items(
    email: Optional[str] = None,
    expiry_date_after: Optional[str] = None,
    insert_date_after: Optional[str] = None,
    quantity_gte: Optional[int] = None
):
    query = {}
    if email:
        query['email'] = email
    if expiry_date_after:
        query["expiry_date"] = {"$gt": datetime.strptime(expiry_date_after, '%Y-%m-%d')}
    if insert_date_after:
        query["insert_date"] = {"$gt": datetime.strptime(insert_date_after, '%Y-%m-%d')}
    if quantity_gte:
        query["quantity"] = {"$gte": quantity_gte}

    items = await db.items.find(query).to_list(100)
    return [
        item_serializer(item) for item in items
    ]

@app.get(
    "/items/aggregate"
)
async def aggregate_items():
    pipeline = [
        {
            "$group": {
                "_id": "$email", 
                "count": {
                    "$sum": 1
                }
            }
        }
    ]

    result = await db.items.aggregate(pipeline).to_list(length=None)
    return result

@app.get(
    "/items/{id}", 
    response_model=dict
)
async def get_item(id: str):
    item = await db.items.find_one({"_id": ObjectId(id)})

    if item:
        return item_serializer(item)

    raise HTTPException(
        status_code=204, 
        detail="Item not found"
    )

@app.put(
    "/items/{id}", 
    response_model=dict
)
async def update_item(
    id: str, 
    update_data: UpdateItem
):
    update_data = {k: v for k, v in update_data.dict().items() if v is not None}
    if "expiry_date" in update_data:
        update_data["expiry_date"] = datetime.strptime(update_data["expiry_date"], '%Y-%m-%d')

    result = await db.items.update_one({"_id": ObjectId(id)}, {"$set": update_data})
    if result.matched_count:
        updated_item = await db.items.find_one({"_id": ObjectId(id)})
        return item_serializer(updated_item)

    raise HTTPException(
        status_code=204, 
        detail="Item not found"
    )

@app.delete(
    "/items/{id}"
)
async def delete_item(id: str):
    result = await db.items.delete_one({"_id": ObjectId(id)})
    if result.deleted_count:
        return {"message": "Item deleted"}

    raise HTTPException(
        status_code=204, 
        detail="Item not found"
    )

# Clock-In Records CRUD APIs

@app.post(
    "/clock-in", 
    response_model=dict
)
async def create_clock_in(
    clock_in: ClockInRecord
):
    clock_in_data = clock_in.dict()
    clock_in_data["insert_datetime"] = datetime.utcnow()

    result = await db.clock_in_records.insert_one(clock_in_data)
    new_record = await db.clock_in_records.find_one({"_id": result.inserted_id})

    return {
        "id": str(new_record["_id"]), 
        "email": new_record["email"], 
        "location": new_record["location"], 
        "insert_datetime": new_record["insert_datetime"]
    }

@app.get(
    "/clock-in/filter", 
    response_model=List[dict]
)
async def filter_clock_in(
    email: Optional[str] = None,
    location: Optional[str] = None,
    insert_datetime_after: Optional[str] = None
):
    query = {}
    if email:
        query["email"] = email
    if location:
        query["location"] = location
    if insert_datetime_after:
        query["insert_datetime"] = {"$gt": datetime.strptime(insert_datetime_after, '%Y-%m-%dT%H:%M:%S')}

    records = await db.clock_in_records.find(query).to_list(100)
    return [
        {
            "id": str(record["_id"]), 
            "email": record["email"], 
            "location": record["location"], 
            "insert_datetime": record["insert_datetime"]
        } for record in records
    ]

@app.get(
    "/clock-in/{id}", 
    response_model=dict
)
async def get_clock_in(id: str):
    clock_in = await db.clock_in_records.find_one({"_id": ObjectId(id)})

    if clock_in:
        return {
            "id": str(clock_in["_id"]), 
            "email": clock_in["email"], 
            "location": clock_in["location"], 
            "insert_datetime": clock_in["insert_datetime"]
        }

    raise HTTPException(
        status_code=204, 
        detail="Clock-in record not found"
    )

@app.put(
    "/clock-in/{id}", 
    response_model=dict
)
async def update_clock_in(
    id: str, 
    update_data: UpdateClockInRecord
):
    update_data = {
        k: v for k, v in update_data.dict().items() if v is not None
    }

    result = await db.clock_in_records.update_one({"_id": ObjectId(id)}, {"$set": update_data})
    if result.matched_count:
        updated_record = await db.clock_in_records.find_one({"_id": ObjectId(id)})
        return {
            "id": str(updated_record["_id"]), 
            "email": updated_record["email"], 
            "location": updated_record["location"], 
            "insert_datetime": updated_record["insert_datetime"]
        }

    raise HTTPException(
        status_code=204, 
        detail="Clock-in record not found"
    )

@app.delete(
    "/clock-in/{id}"
)
async def delete_clock_in(id: str):
    result = await db.clock_in_records.delete_one({"_id": ObjectId(id)})
    if result.deleted_count:
        return {"message": "Clock-in record deleted"}

    raise HTTPException(
        status_code=204, 
        detail="Clock-in record not found"
    )

