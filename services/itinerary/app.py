"""
Itinerary Service - Database API for User Trips and Bookings
=============================================================
Provides REST API for managing user itineraries, trips, and conversation history.
Used by the Travel Planner to get context for intelligent routing.

Uses SQLite for simplicity and consistency with other services.
"""

import os
import logging
from datetime import datetime, date
from typing import Optional, List
from uuid import uuid4
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Text, Integer, DateTime, Date, ForeignKey, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.types import JSON

# OpenTelemetry
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./itinerary.db")
PORT = int(os.getenv("PORT", "8084"))
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "itinerary-service")

# =============================================================================
# OpenTelemetry Setup
# =============================================================================

resource = Resource.create({"service.name": SERVICE_NAME, "service.version": "1.0.0"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

# =============================================================================
# Database Setup
# =============================================================================

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =============================================================================
# SQLAlchemy Models
# =============================================================================

class UserModel(Base):
    __tablename__ = "users"
    
    user_id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    trips = relationship("TripModel", back_populates="user")
    conversations = relationship("ConversationModel", back_populates="user")


class TripModel(Base):
    __tablename__ = "trips"
    
    trip_id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    name = Column(String)
    destination = Column(String)
    origin = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String, default="planning")
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("UserModel", back_populates="trips")
    itinerary_items = relationship("ItineraryItemModel", back_populates="trip")


class ItineraryItemModel(Base):
    __tablename__ = "itinerary_items"
    
    item_id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    trip_id = Column(String, ForeignKey("trips.trip_id"), nullable=False)
    item_type = Column(String, nullable=False)  # flight, hotel, car_rental
    booking_reference = Column(String)
    provider = Column(String)
    status = Column(String, default="pending")
    details = Column(JSON, default=dict)
    check_in = Column(DateTime)
    check_out = Column(DateTime)
    price_cents = Column(Integer)
    currency = Column(String, default="USD")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    trip = relationship("TripModel", back_populates="itinerary_items")


class ConversationModel(Base):
    __tablename__ = "conversations"
    
    conversation_id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    trip_id = Column(String, ForeignKey("trips.trip_id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("UserModel", back_populates="conversations")
    messages = relationship("MessageModel", back_populates="conversation")


class MessageModel(Base):
    __tablename__ = "messages"
    
    message_id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.conversation_id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversation = relationship("ConversationModel", back_populates="messages")

# =============================================================================
# Pydantic Models
# =============================================================================

class UserCreate(BaseModel):
    email: str
    name: str
    preferences: dict = Field(default_factory=dict)

class User(BaseModel):
    user_id: str
    email: str
    name: str
    preferences: dict
    created_at: datetime
    
    class Config:
        from_attributes = True

class TripCreate(BaseModel):
    user_id: str
    name: Optional[str] = None
    destination: str
    origin: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None

class TripUpdate(BaseModel):
    name: Optional[str] = None
    destination: Optional[str] = None
    origin: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class Trip(BaseModel):
    trip_id: str
    user_id: str
    name: Optional[str]
    destination: Optional[str]
    origin: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    status: str
    notes: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class ItineraryItemCreate(BaseModel):
    trip_id: str
    item_type: str
    booking_reference: Optional[str] = None
    provider: Optional[str] = None
    status: str = "pending"
    details: dict = Field(default_factory=dict)
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    price_cents: Optional[int] = None
    currency: str = "USD"

class ItineraryItem(BaseModel):
    item_id: str
    trip_id: str
    item_type: str
    booking_reference: Optional[str]
    provider: Optional[str]
    status: str
    details: dict
    check_in: Optional[datetime]
    check_out: Optional[datetime]
    price_cents: Optional[int]
    currency: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class MessageCreate(BaseModel):
    role: str
    content: str
    metadata: dict = Field(default_factory=dict)

class Message(BaseModel):
    message_id: str
    conversation_id: str
    role: str
    content: str
    metadata: dict
    created_at: datetime
    
    class Config:
        from_attributes = True

class ConversationCreate(BaseModel):
    user_id: str
    trip_id: Optional[str] = None

class Conversation(BaseModel):
    conversation_id: str
    user_id: str
    trip_id: Optional[str]
    messages: List[Message] = []
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserContext(BaseModel):
    user: Optional[User] = None
    active_trip: Optional[Trip] = None
    all_trips: List[Trip] = []
    itinerary: List[ItineraryItem] = []
    recent_messages: List[Message] = []

# =============================================================================
# Database Initialization
# =============================================================================

def init_db():
    """Create tables and seed data"""
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Check if we already have users
        if db.query(UserModel).count() > 0:
            logger.info("Database already seeded, skipping")
            return
        
        logger.info("Seeding database...")
        
        # Create sample users
        users = [
            UserModel(
                user_id="11111111-1111-1111-1111-111111111111",
                email="serena@example.com",
                name="Serena Gomez",
                preferences={"preferred_airline": "Delta", "seat_preference": "window", "hotel_chain": "Marriott", "car_type": "SUV"}
            ),
            UserModel(
                user_id="22222222-2222-2222-2222-222222222222",
                email="john@example.com",
                name="John Smith",
                preferences={"preferred_airline": "United", "seat_preference": "aisle", "hotel_chain": "Hilton", "car_type": "Economy"}
            ),
            UserModel(
                user_id="33333333-3333-3333-3333-333333333333",
                email="alice@example.com",
                name="Alice Johnson",
                preferences={"preferred_airline": "American", "seat_preference": "window", "hotel_chain": "Hyatt", "car_type": "Luxury"}
            ),
        ]
        db.add_all(users)
        db.commit()
        
        # Create sample trips
        trips = [
            TripModel(
                trip_id="aaaa1111-1111-1111-1111-111111111111",
                user_id="11111111-1111-1111-1111-111111111111",
                name="NYC Business Trip",
                destination="New York",
                origin="Los Angeles",
                start_date=date(2026, 3, 10),
                end_date=date(2026, 3, 14),
                status="planning"
            ),
            TripModel(
                trip_id="aaaa2222-2222-2222-2222-222222222222",
                user_id="11111111-1111-1111-1111-111111111111",
                name="Miami Vacation",
                destination="Miami",
                origin="Los Angeles",
                start_date=date(2026, 4, 20),
                end_date=date(2026, 4, 27),
                status="planning"
            ),
            TripModel(
                trip_id="bbbb1111-1111-1111-1111-111111111111",
                user_id="22222222-2222-2222-2222-222222222222",
                name="Chicago Conference",
                destination="Chicago",
                origin="New York",
                start_date=date(2026, 3, 15),
                end_date=date(2026, 3, 18),
                status="booked"
            ),
        ]
        db.add_all(trips)
        db.commit()
        
        # Create sample itinerary items for Chicago trip
        items = [
            ItineraryItemModel(
                item_id="dddd1111-1111-1111-1111-111111111111",
                trip_id="bbbb1111-1111-1111-1111-111111111111",
                item_type="flight",
                booking_reference="UA1234",
                provider="United Airlines",
                status="confirmed",
                details={"flight_number": "UA1234", "origin": "JFK", "destination": "ORD", "departure": "2026-03-15T08:00:00", "arrival": "2026-03-15T10:30:00", "seat": "12A", "class": "Economy"},
                check_in=datetime(2026, 3, 15, 8, 0),
                check_out=datetime(2026, 3, 15, 10, 30),
                price_cents=35000
            ),
            ItineraryItemModel(
                item_id="dddd2222-2222-2222-2222-222222222222",
                trip_id="bbbb1111-1111-1111-1111-111111111111",
                item_type="hotel",
                booking_reference="HIL789456",
                provider="Hilton Chicago",
                status="confirmed",
                details={"hotel_name": "Hilton Chicago", "room_type": "King Suite", "address": "720 S Michigan Ave, Chicago, IL"},
                check_in=datetime(2026, 3, 15, 15, 0),
                check_out=datetime(2026, 3, 18, 11, 0),
                price_cents=89700
            ),
            ItineraryItemModel(
                item_id="dddd3333-3333-3333-3333-333333333333",
                trip_id="bbbb1111-1111-1111-1111-111111111111",
                item_type="flight",
                booking_reference="UA5678",
                provider="United Airlines",
                status="confirmed",
                details={"flight_number": "UA5678", "origin": "ORD", "destination": "JFK", "departure": "2026-03-18T14:00:00", "arrival": "2026-03-18T17:30:00", "seat": "8C", "class": "Economy"},
                check_in=datetime(2026, 3, 18, 14, 0),
                check_out=datetime(2026, 3, 18, 17, 30),
                price_cents=32000
            ),
        ]
        db.add_all(items)
        db.commit()
        
        # Create sample conversation
        conversation = ConversationModel(
            conversation_id="cccc1111-1111-1111-1111-111111111111",
            user_id="11111111-1111-1111-1111-111111111111",
            trip_id="aaaa1111-1111-1111-1111-111111111111"
        )
        db.add(conversation)
        db.commit()
        
        # Add messages
        messages = [
            MessageModel(
                message_id="eeee1111-1111-1111-1111-111111111111",
                conversation_id="cccc1111-1111-1111-1111-111111111111",
                role="user",
                content="I need to plan a business trip to New York",
                metadata_json={"intent": "create_trip"}
            ),
            MessageModel(
                message_id="eeee2222-2222-2222-2222-222222222222",
                conversation_id="cccc1111-1111-1111-1111-111111111111",
                role="assistant",
                content="I'd be happy to help you plan your NYC business trip! I've created a trip for March 10-14. Would you like me to search for flights first?",
                metadata_json={"action": "trip_created"}
            ),
        ]
        db.add_all(messages)
        db.commit()
        
        logger.info("Database seeded successfully with 3 users, 3 trips, 3 itinerary items")
        
    finally:
        db.close()

# =============================================================================
# Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {SERVICE_NAME}")
    logger.info(f"Database: {DATABASE_URL}")
    init_db()
    yield
    logger.info(f"Shutting down {SERVICE_NAME}")

# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="Itinerary Service",
    description="Database API for user trips and bookings (SQLite)",
    version="1.0.0",
    lifespan=lifespan
)

FastAPIInstrumentor.instrument_app(app)

# =============================================================================
# Health Check
# =============================================================================

@app.get("/health")
def health_check():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "service": SERVICE_NAME,
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    }

# =============================================================================
# User Endpoints
# =============================================================================

@app.post("/api/v1/users", response_model=User)
def create_user(user: UserCreate):
    db = SessionLocal()
    try:
        db_user = UserModel(
            email=user.email,
            name=user.name,
            preferences=user.preferences
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return User.model_validate(db_user)
    finally:
        db.close()

@app.get("/api/v1/users/{user_id}", response_model=User)
def get_user(user_id: str):
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return User.model_validate(user)
    finally:
        db.close()

@app.get("/api/v1/users", response_model=List[User])
def list_users():
    db = SessionLocal()
    try:
        users = db.query(UserModel).all()
        return [User.model_validate(u) for u in users]
    finally:
        db.close()

# =============================================================================
# Trip Endpoints
# =============================================================================

@app.post("/api/v1/trips", response_model=Trip)
def create_trip(trip: TripCreate):
    db = SessionLocal()
    try:
        db_trip = TripModel(
            user_id=trip.user_id,
            name=trip.name,
            destination=trip.destination,
            origin=trip.origin,
            start_date=trip.start_date,
            end_date=trip.end_date,
            notes=trip.notes
        )
        db.add(db_trip)
        db.commit()
        db.refresh(db_trip)
        return Trip.model_validate(db_trip)
    finally:
        db.close()

@app.get("/api/v1/trips/{trip_id}", response_model=Trip)
def get_trip(trip_id: str):
    db = SessionLocal()
    try:
        trip = db.query(TripModel).filter(TripModel.trip_id == trip_id).first()
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        return Trip.model_validate(trip)
    finally:
        db.close()

@app.get("/api/v1/users/{user_id}/trips", response_model=List[Trip])
def get_user_trips(user_id: str, status: Optional[str] = None):
    db = SessionLocal()
    try:
        query = db.query(TripModel).filter(TripModel.user_id == user_id)
        if status:
            query = query.filter(TripModel.status == status)
        trips = query.order_by(TripModel.start_date.desc()).all()
        return [Trip.model_validate(t) for t in trips]
    finally:
        db.close()

@app.patch("/api/v1/trips/{trip_id}", response_model=Trip)
def update_trip(trip_id: str, update: TripUpdate):
    db = SessionLocal()
    try:
        trip = db.query(TripModel).filter(TripModel.trip_id == trip_id).first()
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        
        update_data = update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(trip, key, value)
        
        db.commit()
        db.refresh(trip)
        return Trip.model_validate(trip)
    finally:
        db.close()

# =============================================================================
# Itinerary Item Endpoints
# =============================================================================

@app.post("/api/v1/itinerary", response_model=ItineraryItem)
def create_itinerary_item(item: ItineraryItemCreate):
    db = SessionLocal()
    try:
        db_item = ItineraryItemModel(
            trip_id=item.trip_id,
            item_type=item.item_type,
            booking_reference=item.booking_reference,
            provider=item.provider,
            status=item.status,
            details=item.details,
            check_in=item.check_in,
            check_out=item.check_out,
            price_cents=item.price_cents,
            currency=item.currency
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return ItineraryItem.model_validate(db_item)
    finally:
        db.close()

@app.get("/api/v1/trips/{trip_id}/itinerary", response_model=List[ItineraryItem])
def get_trip_itinerary(trip_id: str):
    db = SessionLocal()
    try:
        items = db.query(ItineraryItemModel).filter(
            ItineraryItemModel.trip_id == trip_id
        ).order_by(ItineraryItemModel.check_in).all()
        return [ItineraryItem.model_validate(i) for i in items]
    finally:
        db.close()

@app.patch("/api/v1/itinerary/{item_id}", response_model=ItineraryItem)
def update_itinerary_item(item_id: str, status: Optional[str] = None, booking_reference: Optional[str] = None):
    db = SessionLocal()
    try:
        item = db.query(ItineraryItemModel).filter(ItineraryItemModel.item_id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        if status:
            item.status = status
        if booking_reference:
            item.booking_reference = booking_reference
        
        db.commit()
        db.refresh(item)
        return ItineraryItem.model_validate(item)
    finally:
        db.close()

@app.delete("/api/v1/itinerary/{item_id}")
def delete_itinerary_item(item_id: str):
    db = SessionLocal()
    try:
        item = db.query(ItineraryItemModel).filter(ItineraryItemModel.item_id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        db.delete(item)
        db.commit()
        return {"deleted": True, "item_id": item_id}
    finally:
        db.close()

# =============================================================================
# Conversation Endpoints
# =============================================================================

@app.post("/api/v1/conversations", response_model=Conversation)
def create_conversation(conv: ConversationCreate):
    db = SessionLocal()
    try:
        db_conv = ConversationModel(
            user_id=conv.user_id,
            trip_id=conv.trip_id
        )
        db.add(db_conv)
        db.commit()
        db.refresh(db_conv)
        return Conversation(
            conversation_id=db_conv.conversation_id,
            user_id=db_conv.user_id,
            trip_id=db_conv.trip_id,
            messages=[],
            created_at=db_conv.created_at
        )
    finally:
        db.close()

@app.get("/api/v1/conversations/{conversation_id}", response_model=Conversation)
def get_conversation(conversation_id: str):
    db = SessionLocal()
    try:
        conv = db.query(ConversationModel).filter(
            ConversationModel.conversation_id == conversation_id
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        messages = []
        for m in conv.messages:
            messages.append(Message(
                message_id=m.message_id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                metadata=m.metadata_json or {},
                created_at=m.created_at
            ))
        
        return Conversation(
            conversation_id=conv.conversation_id,
            user_id=conv.user_id,
            trip_id=conv.trip_id,
            messages=messages,
            created_at=conv.created_at
        )
    finally:
        db.close()

@app.post("/api/v1/conversations/{conversation_id}/messages", response_model=Message)
def add_message(conversation_id: str, message: MessageCreate):
    db = SessionLocal()
    try:
        db_msg = MessageModel(
            conversation_id=conversation_id,
            role=message.role,
            content=message.content,
            metadata_json=message.metadata
        )
        db.add(db_msg)
        db.commit()
        db.refresh(db_msg)
        return Message(
            message_id=db_msg.message_id,
            conversation_id=db_msg.conversation_id,
            role=db_msg.role,
            content=db_msg.content,
            metadata=db_msg.metadata_json or {},
            created_at=db_msg.created_at
        )
    finally:
        db.close()

# =============================================================================
# Context Endpoint (Used by Travel Planner)
# =============================================================================

@app.get("/api/v1/users/{user_id}/context", response_model=UserContext)
def get_user_context(
    user_id: str,
    include_completed: bool = Query(False, description="Include completed trips")
):
    """
    Get full context for a user - used by Travel Planner for intelligent routing.
    """
    db = SessionLocal()
    try:
        # Get user
        user = db.query(UserModel).filter(UserModel.user_id == user_id).first()
        user_out = User.model_validate(user) if user else None
        
        # Get trips
        query = db.query(TripModel).filter(TripModel.user_id == user_id)
        if not include_completed:
            query = query.filter(TripModel.status.in_(["planning", "booked"]))
        trips = query.order_by(TripModel.start_date.desc()).all()
        all_trips = [Trip.model_validate(t) for t in trips]
        
        # Find active trip
        active_trip = None
        today = date.today()
        for trip in trips:
            if trip.status == "planning":
                active_trip = Trip.model_validate(trip)
                break
            elif trip.status == "booked" and trip.start_date and trip.start_date >= today:
                active_trip = Trip.model_validate(trip)
                break
        
        # Get itinerary for active trip
        itinerary = []
        if active_trip:
            items = db.query(ItineraryItemModel).filter(
                ItineraryItemModel.trip_id == active_trip.trip_id
            ).order_by(ItineraryItemModel.check_in).all()
            itinerary = [ItineraryItem.model_validate(i) for i in items]
        
        # Get recent messages
        recent_messages = []
        conv = db.query(ConversationModel).filter(
            ConversationModel.user_id == user_id
        ).order_by(ConversationModel.updated_at.desc()).first()
        
        if conv:
            db_messages = db.query(MessageModel).filter(
                MessageModel.conversation_id == conv.conversation_id
            ).order_by(MessageModel.created_at.desc()).limit(10).all()
            
            for m in reversed(db_messages):
                recent_messages.append(Message(
                    message_id=m.message_id,
                    conversation_id=m.conversation_id,
                    role=m.role,
                    content=m.content,
                    metadata=m.metadata_json or {},
                    created_at=m.created_at
                ))
        
        return UserContext(
            user=user_out,
            active_trip=active_trip,
            all_trips=all_trips,
            itinerary=itinerary,
            recent_messages=recent_messages
        )
    finally:
        db.close()

# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
